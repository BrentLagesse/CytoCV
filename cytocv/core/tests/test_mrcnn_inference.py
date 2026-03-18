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
from core.mrcnn.my_inference import predict_images


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
    def _write_listing(listing_path: Path, image_id: str | None = None) -> None:
        lines = ["ImageId, EncodedRLE"]
        if image_id is not None:
            lines.append(f"{image_id}, 4 4")
        listing_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    @staticmethod
    def _write_png(image_path: Path) -> None:
        image_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (4, 4), color=(12, 34, 56)).save(image_path, format="PNG")

    @staticmethod
    def _append_rle_rows(csv_path: Path, image_ids: list[str], encoded_pixels: list[str]) -> None:
        with Path(csv_path).open("a", encoding="utf-8") as handle:
            for image_id, encoded in zip(image_ids, encoded_pixels):
                handle.write(f"{image_id},{encoded}\n")

    @staticmethod
    def _fake_numpy2encoding(
        _pred_masks,
        image_id: str,
        scores=None,
        dilation: bool = True,
    ) -> tuple[list[str], list[str], None]:
        return [image_id], ["1 1"], None

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

    def test_predict_images_returns_none_for_empty_listing_without_loading_runtime(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "run-empty"
            output_dir.mkdir(parents=True, exist_ok=True)
            image_path = output_dir / "sample.png"
            listing_path = output_dir / "preprocessed_images_list.csv"
            self._write_png(image_path)
            self._write_listing(listing_path)

            with patch("core.mrcnn.my_inference.get_inference_runtime") as get_runtime:
                result = predict_images(
                    image_path,
                    listing_path,
                    output_dir,
                    verbose=False,
                )

        self.assertIsNone(result)
        get_runtime.assert_not_called()

    def test_predict_images_returns_none_when_cancelled_before_runtime_load(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "run-cancelled"
            output_dir.mkdir(parents=True, exist_ok=True)

            with patch("core.mrcnn.my_inference.get_inference_runtime") as get_runtime:
                result = predict_images(
                    output_dir / "unused.png",
                    output_dir / "unused.csv",
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

            first_image_path = first_output_dir / "sample-one.png"
            second_image_path = second_output_dir / "sample-two.png"
            first_listing_path = first_output_dir / "preprocessed_images_list.csv"
            second_listing_path = second_output_dir / "preprocessed_images_list.csv"

            self._write_png(first_image_path)
            self._write_png(second_image_path)
            self._write_listing(first_listing_path, "sample-one.png")
            self._write_listing(second_listing_path, "sample-two.png")

            cache_key = InferenceRuntimeKey(Path("C:/weights/deepretina_final.h5"), 1, 2)
            runtime = self._build_fake_runtime(cache_key)

            with patch(
                "core.mrcnn.inference_runtime._resolve_runtime_cache_key",
                return_value=cache_key,
            ), patch(
                "core.mrcnn.inference_runtime._build_inference_runtime",
                return_value=runtime,
            ) as build_runtime, patch(
                "core.mrcnn.my_inference.f.numpy2encoding",
                side_effect=self._fake_numpy2encoding,
            ), patch(
                "core.mrcnn.my_inference.f.write2csv",
                side_effect=self._append_rle_rows,
            ):
                first_result = predict_images(
                    first_image_path,
                    first_listing_path,
                    first_output_dir,
                    verbose=False,
                )
                second_result = predict_images(
                    second_image_path,
                    second_listing_path,
                    second_output_dir,
                    verbose=False,
                )

            self.assertEqual(build_runtime.call_count, 1)
            self.assertEqual(runtime.model.detect.call_count, 2)
            self.assertEqual(
                first_result.read_text(encoding="utf-8").splitlines(),
                ["ImageId, EncodedPixels", "sample-one.png,1 1"],
            )
            self.assertEqual(
                second_result.read_text(encoding="utf-8").splitlines(),
                ["ImageId, EncodedPixels", "sample-two.png,1 1"],
            )
