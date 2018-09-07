"""
general image processing functions
"""

import cv2 as cv
import numpy as np


def detect_sift(gray_img, nfeatures=50):
    """
    :param gray_img:
    :param nfeatures:
    :return:          N x 2 matrix, sift keypoint location in the image
    """

    sift = cv.xfeatures2d.SIFT_create(nfeatures=nfeatures)
    kp = sift.detect(gray_img, None)

    sift_pts = np.zeros((len(kp), 2), dtype=np.float32)
    for i in range(len(kp)):
        sift_pts[i][0] = kp[i].pt[0]
        sift_pts[i][1] = kp[i].pt[1]

    return sift_pts


def detect_compute_sift(im, nfeatures):
    """
    :param im:
    :param nfeatures:
    :return: two lists of key_point (2 dimension), and descriptor (128 dimension)
    """
    sift = cv.xfeatures2d.SIFT_create(nfeatures=nfeatures)
    key_point, descriptor = sift.detectAndCompute(im, None)

    """SIFT may detect more keypoint than set"""

    if len(key_point) > nfeatures:
        key_point = key_point[:nfeatures]
        descriptor = descriptor[:nfeatures]

    return key_point, descriptor


def detect_harris_corner_grid(gray_img, row, column):
    """
    :param gray_img:
    :param row:
    :param column:
    :return: harris corner in shape (n ,2)
    """
    mask = np.zeros_like(gray_img, dtype=np.uint8)

    grid_height = gray_img.shape[0] // row
    grid_width = gray_img.shape[1] // column

    all_harris = np.ndarray([0, 1, 2], dtype=np.float32)

    for i in range(row):
        for j in range(column):
            mask.fill(0)
            grid_y1 = i * grid_height
            grid_x1 = j * grid_width

            if i == row - 1:
                grid_y2 = gray_img.shape[0]
            else:
                grid_y2 = i * grid_height + grid_height

            if j == column - 1:
                grid_x2 = gray_img.shape[1]
            else:
                grid_x2 = j * grid_width + grid_width

            mask[grid_y1:grid_y2, grid_x1:grid_x2] = 1
            grid_harris = cv.goodFeaturesToTrack(gray_img, maxCorners=5,
                                                 qualityLevel=0.2, minDistance=10, mask=mask.astype(np.uint8))

            if grid_harris is not None:
                all_harris = np.concatenate([all_harris, grid_harris], axis=0)

    return all_harris.reshape([-1, 2])


def optical_flow_matching(img, next_img, points, ssd_threshold=20):
    """
    :param img:    current image
    :param next_img: next image
    :param points: points on the current image
    :param ssd_threshold: optical flow parameters
    :return: matched index in the points, points in the next image. two lists
    """
    points = points.reshape((-1, 1, 2))  # 2D matrix to 3D matrix
    next_points, status, err = cv.calcOpticalFlowPyrLK(
        img, next_img, points.astype(np.float32), None, winSize=(31, 31))

    h, w = img.shape[0], img.shape[1]
    matched_index = []

    for i in range(len(next_points)):
        x, y = next_points[i, 0, 0], next_points[i, 0, 1]
        if err[i] < ssd_threshold and 0 < x < w and 0 < y < h:
            matched_index.append(i)

    next_points = np.array([next_points[i, 0] for i in matched_index])

    return matched_index, next_points


def run_ransac(points1, points2, index):
    ransac_mask = np.ndarray([len(points1)])
    _, ransac_mask = cv.findHomography(srcPoints=points1, dstPoints=points2,
                                       ransacReprojThreshold=0.5, method=cv.FM_RANSAC, mask=ransac_mask)
    inner_kp = np.ndarray([0, 2])
    inner_index = np.ndarray([0])

    for j in range(len(points1)):
        if ransac_mask[j] == 1:
            inner_kp = np.row_stack([inner_kp, points2[j]])
            inner_index = np.append(inner_index, index[j])

    return inner_kp, inner_index, ransac_mask


def visualize_points(img, points, pt_color, rad):
    """draw some colored points in img"""
    for j in range(len(points)):
        cv.circle(img, (int(points[j][0]), int(points[j][1])), color=pt_color, radius=rad, thickness=2)


if __name__ == "__main__":
    im = cv.imread('./two_point_calib_dataset/highlights/seq1/0419.jpg', 0)
    print('image shape:', im.shape)

    # unit test
    pts = detect_sift(im, 50)
    print(pts.shape)

    kp, des = detect_compute_sift(im, 50)
    print(len(kp))
    print(len(des))
    print(des[0].shape)

    corners = detect_harris_corner_grid(im, 5, 5)
    print(len(corners))
    print(corners[0].shape)

    im1 = cv.imread('./two_point_calib_dataset/highlights/seq1/0419.jpg', 0)
    im2 = cv.imread('./two_point_calib_dataset/highlights/seq1/0422.jpg', 0)

    pts1 = detect_sift(im1, 50)
    matched_index, next_points = optical_flow_matching(im1, im2, pts1, 20)

    print(len(matched_index), len(next_points))

    cv.imshow('image', im)
    cv.waitKey(0)
    cv.destroyAllWindows()
