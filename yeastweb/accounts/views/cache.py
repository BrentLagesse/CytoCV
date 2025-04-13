from django.core.cache import cache
from core.models import UploadedImage, SegmentedImage, CellStatistics


def get_cache_image(user_id):
    key = 'cached_image'
    value = cache.get(key)

    if value is None or value['id'] != user_id:
        segmented_image = SegmentedImage.objects.filter(user=user_id).order_by('-uploaded_date').first()
        if not segmented_image:
            return None
        uploaded_image = UploadedImage.objects.get(uuid=segmented_image.UUID)
        cells =  CellStatistics.objects.filter(segmented_image_id=segmented_image.UUID).order_by('cell_id')
        cell_stat = []
        for cell in cells:
            cell_stat.append(cell)

        value = {
            'id' : user_id,
            'segmented' : segmented_image,
            'uploaded' : uploaded_image,
            'cell' : cell_stat,
        }
        cache.set(key, value, 60 * 10) # 10 minutes timeout

    return value

