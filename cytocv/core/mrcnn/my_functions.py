"""Legacy Mask R-CNN mask helpers kept as a compatibility facade.

Runtime inference now delegates duplicate removal and mask cleanup to
``mask_processing``. These wrappers preserve the older function names used by
legacy scripts while sharing the same post-processing rules as active inference.
"""

import numpy as np
import pandas as pd

from .mask_processing import (
    DEFAULT_MASK_DUPLICATE_THRESHOLD,
    postprocess_prediction_masks,
    remove_duplicate_masks,
)

def run_length_encoding(x):
    """Encode one binary mask using the Kaggle-style column-major RLE format."""

    dots = np.where(x.T.flatten() == 1)[0]
    run_lengths = []
    prev = -2
    for b in dots:
        if (b>prev+1): run_lengths.extend((b + 1, 0))
        run_lengths[-1] += 1
        prev = b
    run_lengths = ' '.join([str(r) for r in run_lengths])
    return run_lengths



def remove_duplicate(mask,threshold=DEFAULT_MASK_DUPLICATE_THRESHOLD,scores =None):
    """Compatibility wrapper for score-aware duplicate-mask removal."""

    return remove_duplicate_masks(mask, threshold=threshold, scores=scores)
    

    
def numpy2encoding(predicts, img_name, scores=None,threshold=DEFAULT_MASK_DUPLICATE_THRESHOLD,dilation=False):
    """Post-process an instance mask volume and return image ids plus RLE strings."""

    predicts = postprocess_prediction_masks(
        predicts,
        scores=scores,
        threshold=threshold,
        dilation=dilation,
    )
    ImageId = []
    EncodedPixels = []
    for i in range(predicts.shape[2]): 
        rle = run_length_encoding(predicts[:,:,i])
        
        if len(rle)>0:
            ImageId.append(img_name)
            EncodedPixels.append(rle)    
    return ImageId, EncodedPixels, predicts


def write2csv(file, ImageId, EncodedPixels):
    """Append encoded mask rows to the historical submission CSV shape."""

    df = pd.DataFrame({ 'ImageId' : ImageId , 'EncodedPixels' : EncodedPixels})
    with open(file, 'a', newline='') as f:
         df.to_csv(f, index=False, columns=['ImageId', 'EncodedPixels'], header=False)

    
