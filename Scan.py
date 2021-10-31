import cv2
import numpy as np
from PIL import Image


async def ScanDoc(filepath):
    img = cv2.imread(filepath, -1)

    rgb_planes = cv2.split(img)

    # result_planes = []
    result_norm_planes = []
    # result_norm_improve_planes = []
    for plane in rgb_planes:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
        dilated_img = cv2.dilate(plane, np.ones((7, 7), np.uint8))
        bg_img = cv2.medianBlur(dilated_img, 21)
        diff_img = 255 - cv2.absdiff(plane, bg_img)
        norm_img = cv2.normalize(diff_img, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX, dtype=cv2.CV_8UC1)

        # thr_img = cv2.adaptiveThreshold(norm_img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31,
        # 8) norm_img_imp = cv2.normalize(thr_img, thr_img, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX,
        # dtype=cv2.CV_8UC1)
        norm_img = cv2.resize(norm_img, None, fx=2, fy=2, interpolation=cv2.INTER_AREA)
        # norm_img_imp = cv2.resize(norm_img_imp, None, fx=2, fy=2, interpolation=cv2.INTER_AREA)

        # result_planes.append(diff_img)
        result_norm_planes.append(norm_img)
        # result_norm_improve_planes.append(norm_img_imp)

    # result = cv2.merge(result_planes)
    result_norm = cv2.merge(result_norm_planes)
    # result_norm_improve = cv2.merge(result_norm_improve_planes)

    # cv2.imwrite('shadows_out.png', result)
    cv2.imwrite(filepath, result_norm)
    # cv2.imwrite('shadows_out_improve.png', result_norm_improve)
    return 'Done'


async def ToPdf(filepath):
    image1 = Image.open(filepath)
    im1 = image1.convert('RGB')
    datachanged = filepath.replace('.jpg', '')
    im1.save(datachanged + '.pdf')


async def QReader(filepath):
    image = cv2.imread(filepath)

    qrCodeDetector = cv2.QRCodeDetector()

    decodedText, points, _ = qrCodeDetector.detectAndDecode(image)

    if points is not None:

        nrOfPoints = len(points)

        for i in range(nrOfPoints):
            nextPointIndex = (i + 1) % nrOfPoints
            cv2.line(image, tuple(points[i][0]), tuple(points[nextPointIndex][0]), (255, 0, 0), 5)

        return decodedText
    else:
        return 'QR code not detected'
