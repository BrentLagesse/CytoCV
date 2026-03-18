from __future__ import annotations

import threading
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
from django.test import SimpleTestCase
from PIL import Image

from core.mrcnn.inference_runtime import (
    InferenceRuntimeKey,
    _resolve_runtime_cache_key,
    clear_inference_runtime_cache,
    get_inference_runtime,
)
from core.mrcnn.mask_processing import (
    build_labeled_mask_image,
    postprocess_prediction_masks,
)
from core.mrcnn.my_inference import predict_images
from core.mrcnn.preprocess_images import PreprocessedImageArtifact


class InferenceRuntimeCacheTests(SimpleTestCase):
    def tearDown(self):
        clear_inference_runtime_cache()
        super().tearDown()

    def test_resolve_runtime_cache_key_uses_weights_path_and_metadata(self):
        with TemporaryDirectory() as temp_dir:
            weights_path = Path(temp_dir) / "deepretina_final.h5"
            weights_path.write_bytes(b"weights")

            with patch(
                "core.mrcnn.inference_runtime._resolve_weights_path",
                return_value=weights_path.resolve(),
            ):
                cache_key = _resolve_runtime_cache_key()

            stat_result = weights_path.stat()
            self.assertEqual(cache_key.weights_path, weights_path.resolve())
            self.assertEqual(cache_key.weights_size, stat_result.st_size)
            self.assertEqual(
                cache_key.weights_mtime_ns,
                getattr(stat_result, "st_mtime_ns", int(stat_result.st_mtime * 1_000_000_000)),
            )

    def test_get_inference_runtime_builds_once_when_weights_key_is_unchanged(self):
        cache_key = InferenceRuntimeKey(Path("C:/weights/deepretina_final.h5"), 1, 2)
        runtime = SimpleNamespace(cache_key=cache_key)

        with patch(
            "core.mrcnn.inference_runtime._resolve_runtime_cache_key",
            return_value=cache_key,
        ), patch(
            "core.mrcnn.inference_runtime._build_inference_runtime",
            return_value=runtime,
        ) as build_runtime:
            first_runtime = get_inference_runtime()
            second_runtime = get_inference_runtime()

        self.assertIs(first_runtime, runtime)
        self.assertIs(second_runtime, runtime)
        build_runtime.assert_called_once_with(cache_key)

    def test_get_inference_runtime_rebuilds_when_weights_key_changes(self):
        first_key = InferenceRuntimeKey(Path("C:/weights/deepretina_final.h5"), 1, 2)
        second_key = InferenceRuntimeKey(Path("C:/weights/deepretina_final.h5"), 3, 2)
        first_runtime = SimpleNamespace(cache_key=first_key)
        second_runtime = SimpleNamespace(cache_key=second_key)

        with patch(
            "core.mrcnn.inference_runtime._resolve_runtime_cache_key",
            side_effect=[first_key, second_key],
        ), patch(
            "core.mrcnn.inference_runtime._build_inference_runtime",
            side_effect=[first_runtime, second_runtime],
        ) as build_runtime:
            self.assertIs(get_inference_runtime(), first_runtime)
            self.assertIs(get_inference_runtime(), second_runtime)

        self.assertEqual(build_runtime.call_count, 2)
        self.assertEqual(
            [call.args[0] for call in build_runtime.call_args_list],
            [first_key, second_key],
        )


class PredictImagesRuntimeReuseTests(SimpleTestCase):
    def tearDown(self):
        clear_inference_runtime_cache()
        super().tearDown()

    @staticmethod
    def _build_artifact(output_dir: Path, *, image_name: str) -> PreprocessedImageArtifact:
        image_path = output_dir / image_name
        image_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (4, 4), color=(12, 34, 56)).save(image_path, format="PNG")
        return PreprocessedImageArtifact(
            image_id=image_name,
            preprocessed_path=image_path,
            original_height=4,
            original_width=4,
        )

    @staticmethod
    def _build_fake_runtime(cache_key: InferenceRuntimeKey) -> SimpleNamespace:
        fake_results = [
            {
                "masks": np.ones((4, 4, 1), dtype=np.uint8),
                "scores": np.array([0.99], dtype=np.float32),
                "class_ids": np.array([1], dtype=np.int32),
            }
        ]
        return SimpleNamespace(
            cache_key=cache_key,
            tensorflow=SimpleNamespace(random=SimpleNamespace(set_seed=Mock())),
            model=SimpleNamespace(detect=Mock(return_value=fake_results)),
            detect_lock=threading.Lock(),
        )

    def test_postprocess_prediction_masks_applies_dilation_and_duplicate_removal_without_mutation(self):
        pred_masks = np.zeros((5, 5, 2), dtype=np.uint8)
        pred_masks[2, 2, 0] = 1
        pred_masks[2, 2, 1] = 1
        original_masks = np.array(pred_masks, copy=True)

        processed_masks = postprocess_prediction_masks(
            pred_masks,
            scores=np.array([0.1, 0.9], dtype=np.float32),
            dilation=True,
        )

        self.assertTrue(np.array_equal(pred_masks, original_masks))
        self.assertGreater(int(processed_masks[:, :, 0].sum()), 1)
        self.assertFalse(np.any(processed_masks[:, :, 1]))

    def test_build_labeled_mask_image_preserves_surviving_original_order(self):
        pred_masks = np.zeros((4, 4, 3), dtype=np.uint8)
        pred_masks[1, 1, 0] = 1
        pred_masks[1, 1, 1] = 1
        pred_masks[3, 3, 2] = 1

        label_image = build_labeled_mask_image(
            pred_masks,
            scores=np.array([0.1, 0.9, 0.8], dtype=np.float32),
        )

        self.assertEqual(label_image.dtype, np.uint16)
        self.assertEqual(int(label_image[1, 1]), 1)
        self.assertEqual(int(label_image[3, 3]), 2)

    def test_build_labeled_mask_image_returns_blank_uint16_for_empty_predictions(self):
        label_image = build_labeled_mask_image(np.zeros((4, 4, 0), dtype=np.uint8))

        self.assertEqual(label_image.dtype, np.uint16)
        self.assertTrue(np.array_equal(label_image, np.zeros((4, 4), dtype=np.uint16)))

    def test_predict_images_writes_blank_mask_when_model_returns_no_detections(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "run-empty"
            output_dir.mkdir(parents=True, exist_ok=True)
            artifact = self._build_artifact(output_dir, image_name="sample.png")
            runtime = SimpleNamespace(
                tensorflow=SimpleNamespace(random=SimpleNamespace(set_seed=Mock())),
                model=SimpleNamespace(
                    detect=Mock(
                        return_value=[
                            {
                                "masks": np.zeros((4, 4, 0), dtype=np.uint8),
                                "scores": np.array([], dtype=np.float32),
                                "class_ids": np.array([], dtype=np.int32),
                            }
                        ]
                    )
                ),
                detect_lock=threading.Lock(),
            )

            with patch(
                "core.mrcnn.my_inference.get_inference_runtime",
                return_value=runtime,
            ) as get_runtime:
                result = predict_images(
                    artifact,
                    output_dir,
                    verbose=False,
                )

            self.assertIsNotNone(result)
            self.assertTrue(result.exists())
            self.assertEqual(np.array(Image.open(result)).dtype, np.uint16)
            self.assertTrue(
                np.array_equal(
                    np.array(Image.open(result)),
                    np.zeros((4, 4), dtype=np.uint16),
                )
            )
            get_runtime.assert_called_once()

    def test_predict_images_returns_none_when_cancelled_before_runtime_load(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "run-cancelled"
            output_dir.mkdir(parents=True, exist_ok=True)
            artifact = PreprocessedImageArtifact(
                image_id="cancelled.png",
                preprocessed_path=output_dir / "unused.png",
                original_height=4,
                original_width=4,
            )

            with patch("core.mrcnn.my_inference.get_inference_runtime") as get_runtime:
                result = predict_images(
                    artifact,
                    output_dir,
                    verbose=False,
                    cancel_check=lambda: True,
                )

        self.assertIsNone(result)
        get_runtime.assert_not_called()

    def test_predict_images_reuses_cached_runtime_across_separate_runs(self):
        with TemporaryDirectory() as temp_dir:
            root_dir = Path(temp_dir)
            first_output_dir = root_dir / "run-one"
            second_output_dir = root_dir / "run-two"
            first_output_dir.mkdir(parents=True, exist_ok=True)
            second_output_dir.mkdir(parents=True, exist_ok=True)

            first_artifact = self._build_artifact(first_output_dir, image_name="sample-one.png")
            second_artifact = self._build_artifact(second_output_dir, image_name="sample-two.png")

            cache_key = InferenceRuntimeKey(Path("C:/weights/deepretina_final.h5"), 1, 2)
            runtime = self._build_fake_runtime(cache_key)

            with patch(
                "core.mrcnn.inference_runtime._resolve_runtime_cache_key",
                return_value=cache_key,
            ), patch(
                "core.mrcnn.inference_runtime._build_inference_runtime",
                return_value=runtime,
            ) as build_runtime:
                first_result = predict_images(
                    first_artifact,
                    first_output_dir,
                    verbose=False,
                )
                second_result = predict_images(
                    second_artifact,
                    second_output_dir,
                    verbose=False,
                )

            self.assertEqual(build_runtime.call_count, 1)
            self.assertEqual(runtime.model.detect.call_count, 2)
            self.assertEqual(first_result.name, "mask.tif")
            self.assertEqual(second_result.name, "mask.tif")
            self.assertTrue(np.array_equal(np.array(Image.open(first_result)), np.ones((4, 4), dtype=np.uint16)))
            self.assertTrue(np.array_equal(np.array(Image.open(second_result)), np.ones((4, 4), dtype=np.uint16)))
