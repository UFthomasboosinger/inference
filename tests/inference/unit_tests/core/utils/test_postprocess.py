import numpy as np
import pytest

from inference.core.exceptions import PostProcessingError
from inference.core.utils.postprocess import (
    cosine_similarity,
    crop_mask,
    standardise_static_crop,
    get_static_crop_dimensions,
    shift_bboxes,
    clip_boxes_coordinates,
    undo_image_padding_for_predicted_boxes,
    stretch_crop_predictions,
    post_process_bboxes,
    sigmoid,
    scale_bboxes,
    undo_image_padding_for_predicted_polygons,
    scale_polygons,
    post_process_polygons,
)


def test_cosine_similarity_against_vectors() -> None:
    # given
    a = np.array([1, 0])
    b = np.array([0, 1])

    # when
    result = cosine_similarity(a=a, b=b)

    # then
    assert abs(result) < 1e-5


def test_cosine_similarity_orthogonal_vectors() -> None:
    # given
    a = np.array([1, 0])
    b = np.array([-2, 0])

    # when
    result = cosine_similarity(a=a, b=b)

    # then
    assert abs(result + 1) < 1e-5


def test_cosine_similarity_against_semi_aligned_vectors() -> None:
    # given
    a = np.array([5, 5])
    b = np.array([1, 0])

    # when
    result = cosine_similarity(a=a, b=b)

    # then
    assert abs(result - np.sqrt(2) / 2) < 1e-5


def test_cosine_similarity_against_bunch_of_vectors() -> None:
    # given
    a = np.array([[1, 0], [1, 0], [5, 5]])
    b = np.array([[0, 1], [-2, 0], [1, 0]])

    # when
    with pytest.raises(ValueError):
        # does not work against multiple vectors at once
        _ = cosine_similarity(a=a, b=b)


def test_crop_mask() -> None:
    # given
    masks = np.ones((2, 128, 128))
    boxes = np.array([[32, 32, 64, 64], [64, 64, 96, 96]])
    expected_result = np.zeros((2, 128, 128))
    expected_result[0, 32:64, 32:64] = 1
    expected_result[1, 64:96, 64:96] = 1

    # when
    result = crop_mask(masks=masks, boxes=boxes)

    # then
    assert result.shape == expected_result.shape
    assert np.allclose(result, expected_result)


def test_standardise_static_crop() -> None:
    # when
    result = standardise_static_crop(
        static_crop_config={"x_min": 15, "y_min": 20, "x_max": 50, "y_max": 75}
    )

    # then
    assert np.allclose(result, [0.15, 0.2, 0.5, 0.75])


def test_get_static_crop_dimensions_when_misconfiguration_happens() -> None:
    # when
    with pytest.raises(PostProcessingError):
        _ = get_static_crop_dimensions(
            orig_shape=(256, 256),
            preproc={"static-crop": {}},
        )


def test_get_static_crop_dimensions_when_no_crop_should_be_applied() -> None:
    # when
    result = get_static_crop_dimensions(
        orig_shape=(256, 256),
        preproc={},
    )

    # then
    assert result == ((0, 0), (256, 256))


def test_get_static_crop_dimensions_when_crop_should_be_applied() -> None:
    # when
    result = get_static_crop_dimensions(
        orig_shape=(200, 100),
        preproc={
            "static-crop": {
                "enabled": True,
                "x_min": 15,
                "y_min": 20,
                "x_max": 50,
                "y_max": 75,
            }
        },
    )

    # then
    assert result == ((15, 40), (35, 110))


def test_apply_crop_shift_to_boxes() -> None:
    # given
    predicted_bboxes = np.array(
        [
            [20, 20, 40, 40],
            [30, 60, 90, 120],
        ]
    )
    expected_result = np.array(
        [
            [30, 40, 50, 60],
            [40, 80, 100, 140],
        ]
    )

    # when
    result = shift_bboxes(
        bboxes=predicted_bboxes,
        shift_x=10,
        shift_y=20,
    )

    # then
    assert result.shape == expected_result.shape
    assert np.allclose(result, expected_result)


def test_clip_boxes_coordinates() -> None:
    # given
    predicted_bboxes = np.array(
        [
            [-0.1, 20, 40, 40.1, 0.9],
            [30, 60.1, 90, 120.1, 0.9],
        ]
    )
    expected_result = np.array(
        [
            [0, 20, 40, 40, 0.9],
            [30, 60, 80, 120, 0.9],
        ]
    )

    # when
    result = clip_boxes_coordinates(
        predicted_bboxes=predicted_bboxes,
        origin_shape=(80, 120),
    )
    assert result.shape == expected_result.shape
    assert np.allclose(result, expected_result)


def test_undo_image_padding_for_predicted_boxes() -> None:
    # given
    predicted_bboxes = np.array(
        [
            [20, 32, 40, 64],
            [30, 64, 90, 128],
        ],
        dtype=np.float32,
    )
    # scaling factor for inference is 0.5, padding of 16px along OY axis added
    expected_result = np.array(
        [
            [8, 64, 48, 128],
            [28, 128, 148, 256],
        ],
        dtype=np.float32,
    )

    # when
    result = undo_image_padding_for_predicted_boxes(
        predicted_bboxes=predicted_bboxes,
        infer_shape=(128, 128),
        origin_shape=(192, 256),
    )

    # then
    assert result.shape == expected_result.shape
    assert np.allclose(result, expected_result)


def test_stretch_crop_predictions() -> None:
    # given
    predicted_bboxes = np.array(
        [
            [20, 32, 40, 64],
            [30, 64, 90, 128],
        ],
        dtype=np.float32,
    )
    expected_result = np.array(
        [
            [5, 16, 10, 32],
            [7.5, 32, 22.5, 64],
        ],
        dtype=np.float32,
    )

    # when
    result = stretch_crop_predictions(
        predicted_bboxes=predicted_bboxes,
        infer_shape=(128, 128),
        crop_shape=(32, 64),
    )

    # then
    assert result.shape == expected_result.shape
    assert np.allclose(result, expected_result)


def test_post_process_bboxes_when_crop_with_stretch_used() -> None:
    # given
    predicted_bboxes = [
        np.array(
            [
                [20, 32, 40, 64, 0.9],
                [30, 64, 88, 128, 0.85],
            ],
            dtype=np.float32,
        ).tolist()
    ]
    # there is a crop from (x=20, y=40) to (x=84, y=104) (box size - h=64, w=64)
    # compared to inference size (128, 128) and we stretch, such that OX scale is 2.0,
    # OY scale is 2.0, then we shift by crop (OX +20, OY +40)
    # for OX coord we take input ox / 2 + 20, for OY: input oy / 2 +  40
    expected_result = np.expand_dims(
        np.array(
            [
                [30, 56, 40, 72, 0.9],
                [35, 72, 64, 104, 0.85],
            ],
            dtype=np.float32,
        ),
        axis=0,
    )

    # when
    result = post_process_bboxes(
        predictions=predicted_bboxes,
        infer_shape=(128, 128),
        img_dims=[(200, 100)],
        preproc={
            "static-crop": {
                "enabled": True,
                "x_min": 20,
                "y_min": 20,
                "x_max": 84,
                "y_max": 52,
            }
        },
    )

    # then
    assert np.array(result).shape == (1, 2, 5)
    assert np.allclose(np.array(result), expected_result)


def test_post_process_bboxes_when_crop_with_padding_used() -> None:
    # given
    predicted_bboxes = [
        np.array(
            [
                [32, 32, 40, 64, 0.9],
                [32, 64, 88, 128, 0.85],
            ],
            dtype=np.float32,
        ).tolist()
    ]
    # there is a crop from (x=40, y=40) to (x=72, y=104) of size(h=64, w=32)
    # compared to inference size (128, 128) - crop will be given 32 padding on OX axis each side
    # we need to upscale 2x prediction coordinates
    # crop shift +40, +40 in each axis
    expected_result = np.expand_dims(
        np.array(
            [
                [40, 56, 44, 72, 0.9],
                [40, 72, 68, 104, 0.85],
            ],
            dtype=np.float32,
        ),
        axis=0,
    )

    # when
    result = post_process_bboxes(
        predictions=predicted_bboxes,
        infer_shape=(128, 128),
        img_dims=[(200, 200)],
        preproc={
            "static-crop": {
                "enabled": True,
                "x_min": 20,
                "y_min": 20,
                "x_max": 36,
                "y_max": 52,
            }
        },
        resize_method="Fit (black edges) in",
    )

    # then
    assert np.array(result).shape == (1, 2, 5)
    assert np.allclose(np.array(result), expected_result)


@pytest.mark.parametrize(
    "x, expected_result",
    [
        (0.0, 0.5),
        (1.0, 0.73105),
        (-1.0, 0.26894),
        (np.array([0.0, 1.0, -1.0]), np.array([0.5, 0.73105, 0.26894])),
    ],
)
def test_sigmoid(x: float, expected_result: float) -> None:
    # when
    result = sigmoid(x)

    # then
    assert np.allclose(result, expected_result, rtol=1e-4)


@pytest.mark.parametrize(
    "bboxes, scale_x, scale_y, expected_result",
    [
        (
            np.array([[1.0, 2, 3, 4], [5, 6, 7, 8]]),
            2.0,
            4.0,
            np.array([[2.0, 8, 6, 16], [10, 24, 14, 32]]),
        ),
        (
            np.array([[1.0, 2, 3, 4], [5, 6, 7, 8]]),
            1.0,
            1.0,
            np.array([[1.0, 2, 3, 4], [5, 6, 7, 8]]),
        ),
        (
            np.array([[1.0, 2, 3, 4], [5, 6, 7, 8]]),
            0.5,
            0.5,
            np.array([[0.5, 1.0, 1.5, 2], [2.5, 3, 3.5, 4]]),
        ),
    ],
)
def test_scale_bboxes(
    bboxes: np.ndarray,
    scale_x: float,
    scale_y: float,
    expected_result: np.ndarray,
) -> None:
    # when
    result = scale_bboxes(bboxes=bboxes, scale_x=scale_x, scale_y=scale_y)

    # then
    assert np.allclose(result, expected_result)


def test_undo_image_padding_for_predicted_polygons() -> None:
    # given
    polygons = [[(64, 20), (74, 30), (84, 40)], [(94, 50), (104, 60), (114, 70)]]
    # there is OX padding of size 64 each side, so effectively 64 to be deduced from x coordinates
    expected_result = np.array(
        [[(0, 20), (10, 30), (20, 40)], [(30, 50), (40, 60), (50, 70)]]
    )

    # when
    result = undo_image_padding_for_predicted_polygons(
        polygons=polygons,
        img0_shape=(128, 256),
        img1_shape=(256, 256),
    )

    # then
    assert np.allclose(np.array(result), expected_result)


def test_scale_polygons() -> None:
    # given
    polygons = [[(10, 20), (20, 30), (30, 40)], [(40, 50), (50, 60), (60, 70)]]
    expected_result = np.array(
        [[(20, 10), (40, 15), (60, 20)], [(80, 25), (100, 30), (120, 35)]]
    )

    # when
    result = scale_polygons(
        polygons=polygons,
        x_scale=2.0,
        y_scale=0.5,
    )

    # then
    assert np.allclose(np.array(result), expected_result)


def test_post_process_polygons_when_stretching_resize_used() -> None:
    # given
    polygons = [[(10, 20), (20, 30), (30, 40)], [(40, 50), (50, 60), (60, 70)]]
    # there is a crop from (x=10, y=20) to (x=90, y=180) (box size - h=160, w=80)
    # compared to inference size (100, 100) and we stretch, such that OX scale is 1.25,
    # OY scale is 0.625, then we shift by crop (OX +10, OY +20)
    # for OX coord we take input ox / 1.25 + 10, for OY: input oy / 0.625 +  20
    expected_result = np.array(
        [[(18, 52), (26, 68), (34, 84)], [(42, 100), (50, 116), (58, 132)]]
    )

    # when
    result = post_process_polygons(
        img1_shape=(100, 100),
        polys=polygons,
        img0_shape=(200, 100),
        preproc={
            "static-crop": {
                "enabled": True,
                "x_min": 10,
                "y_min": 10,
                "x_max": 90,
                "y_max": 90,
            }
        },
    )

    # then
    assert np.allclose(np.array(result), expected_result)


def test_post_process_polygons_when_fit_resize_used() -> None:
    # given
    polygons = [[(25, 20), (35, 30), (45, 40)], [(55, 50), (65, 60), (75, 70)]]
    # there is a crop from (x=10, y=20) to (x=90, y=180) (box size - h=160, w=80)
    # compared to inference size (100, 100) and we add padding - initially 40px on OX,
    # but after that we resize to (100, 100), so effective padding is 25px
    # Any valid prediction starts from 25 on OX and end at 75.
    # up-scaling to original crops coordinates - multiplying by 1.6
    # At the end - crop shift to be applied: (OX +10, OY +20)
    # for OX coord we take input (ox - 25) * 1.6 + 10, for OY: input oy * 1.6 +  20
    expected_result = np.array(
        [[(10, 52), (26, 68), (42, 84)], [(58, 100), (74, 116), (90, 132)]]
    )

    # when
    result = post_process_polygons(
        img1_shape=(100, 100),
        polys=polygons,
        img0_shape=(200, 100),
        preproc={
            "static-crop": {
                "enabled": True,
                "x_min": 10,
                "y_min": 10,
                "x_max": 90,
                "y_max": 90,
            }
        },
        resize_method="Fit (black edges) in",
    )

    # then
    assert np.allclose(np.array(result), expected_result)