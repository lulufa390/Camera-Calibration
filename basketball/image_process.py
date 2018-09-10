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


def detect_compute_sift(im, nfeatures, verbose = False):
    """
    :param im:
    :param nfeatures:
    :return: two lists of key_point (2 dimension), and descriptor (128 dimension)
    """
    sift = cv.xfeatures2d.SIFT_create(nfeatures=nfeatures)
    key_point, descriptor = sift.detectAndCompute(im, None)

    """SIFT may detect more keypoint than set"""

    if nfeatures > 0 and len(key_point) > nfeatures:
        key_point = key_point[:nfeatures]
        descriptor = descriptor[:nfeatures]

    if verbose == True:
        print('detect: %d SIFT keypoints.' % len(key_point))

    return key_point, descriptor

def match_sift_features(keypiont1, descriptor1, keypoint2, descriptor2, verbose = False):
    # from https://opencv-python-tutroals.readthedocs.io/en
    # /latest/py_tutorials/py_feature2d/py_feature_homography/py_feature_homography.html
    """
    :param keypiont1: list of keypoints
    :param descrpitor1:
    :param keypoint2:
    :param descriptor2:
    :param verbose:
    :return: matched 2D points, and matched descriptor index
    :inlier_matches: for visualization purpose
    """

    bf = cv.BFMatcher()
    matches = bf.knnMatch(descriptor1, descriptor2, k=2) # (query_data, train_data)

    # step 1: apply ratio test
    good = []
    for m, n in matches:
        if m.distance < 0.7 * n.distance:
            good.append(m)

    if verbose == True:
        print('%d matches passed the ratio test' % len(good))

    N = len(good)
    pts1 = np.zeros((N, 2))
    pts2 = np.zeros((N, 2))
    index1 = np.zeros((N), dtype=np.int32)
    index2 = np.zeros((N), dtype=np.int32)
    for i in range(N):
        idx1, idx2 = good[i].queryIdx, good[i].trainIdx  # query is from the first image
        index1[i], index2[i] = idx1, idx2
        pts1[i] = keypiont1[idx1].pt
        pts2[i] = keypoint2[idx2].pt

    # step 2: apply homography constraint
    # inlier index from homography estimation
    inlier_index = homography_ransac(pts1, pts2, 1.0)

    if verbose == True:
        print('%d matches passed the homography ransac' % len(inlier_index))

    pts1, pts2 = pts1[inlier_index, :], pts2[inlier_index, :]
    index1 = index1[inlier_index].tolist()
    index2 = index2[inlier_index].tolist()  #@todo, index1 and index2 is not tested

    return pts1, index1, pts2, index2 #, inlier_matches


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

def homography_ransac(points1, points2, reprojection_threshold = 0.5):
    """
    :param points1: N x 2 matched points
    :param points2:
    :return: list, matched index in original points, [0, 3, 4...]
    """
    ransac_mask = np.ndarray([len(points1)])
    _, ransac_mask = cv.findHomography(srcPoints=points1, dstPoints=points2,
                                       ransacReprojThreshold=reprojection_threshold, method=cv.FM_RANSAC, mask=ransac_mask)
    inner_kp = np.ndarray([0, 2])
    inner_index = np.ndarray([0])

    index = [i for i in range(len(ransac_mask)) if ransac_mask[i] == 1]
    return index

def run_ransac(points1, points2, index):
    """
    :param points1: N x 2 array, float32 or float64
    :param points2:
    :param index:
    :return:
    """
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


def draw_matches(im1, im2, pts1, pts2):
    """
    :param im1: RGB image
    :param im2:
    :param pts1:  points in image 1
    :param pts2:  points in image 2
    :return: lines overlaid on the original image
    """
    # step 1: horizontal concat image
    vis = np.concatenate((im1, im2), axis=1)
    w = im1.shape[1]
    N = pts1.shape[0]
    # step 2:draw lines
    for i in range(N):
        p1, p2 = pts1[i], pts2[i]
        p2[0] += w
        p1 = p1.astype(np.int32)
        p2 = p2.astype(np.int32)
        cv.line(vis, (p1[0], p1[1]), (p2[0], p2[1]), (0, 255, 0), thickness=1)
    return vis





def get_overlap_index(index1, index2):
    index1_overlap = np.ndarray([0], np.int8)
    index2_overlap = np.ndarray([0], np.int8)
    ptr1 = 0
    ptr2 = 0
    while ptr1 < len(index1) and ptr2 < len(index2):
        if index1[ptr1] == index2[ptr2]:
            index1_overlap = np.append(index1_overlap, ptr1)
            index2_overlap = np.append(index2_overlap, ptr2)
            ptr1 += 1
            ptr2 += 1
        elif index1[ptr1] < index2[ptr2]:
            ptr1 += 1
        elif index1[ptr1] > index2[ptr2]:
            ptr2 += 1
    return index1_overlap, index2_overlap


def ut_match_sift_features():
    im1 = cv.imread('/Users/jimmy/Desktop/ptz_slam_dataset/basketball/images/00084000.jpg', 1)
    im2 = cv.imread('/Users/jimmy/Desktop/ptz_slam_dataset/basketball/images/00084660.jpg', 1)

    im1_gray = cv.cvtColor(im1, cv.COLOR_BGR2GRAY)
    im2_gray = cv.cvtColor(im2, cv.COLOR_BGR2GRAY)
    kp1, des1 = detect_compute_sift(im1_gray, 0, True)
    kp2, des2 = detect_compute_sift(im2_gray, 0, True)

    print(type(des1[0]))
    print(des1[0].shape)

    pt1, index1, pt2, index2 = match_sift_features(kp1, des1, kp2, des2, True)

    im3 = draw_matches(im1, im2, pt1, pt2)
    cv.imshow('matches', im3)
    cv.waitKey(0)



    #print('image shape:', im1.shape)


def ut_redundant():
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

if __name__ == "__main__":
    ut_match_sift_features()