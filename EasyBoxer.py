import logging
import os
import re
import sys
from datetime import datetime
from glob import glob
from pathlib import Path
import cv2
import numpy as np
from natsort import natsorted
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtTest import QTest
from send2trash import send2trash


def log(path='./logs', test=False):
    

    logs = logging.getLogger()
    logs.setLevel(logging.DEBUG)

    ch = logging.StreamHandler()  # print console
    logs.addHandler(ch)

    if test:
        p = Path(path)
        p.mkdir(exist_ok=True)
        fh = logging.FileHandler(filename=p / "logfile.log")  # logging file
        fh.setLevel(logging.WARNING)  # only logging over warning level
        fh.setFormatter(logging.Formatter("%(levelname)s %(asctime)s - %(message)s"))
        logs.addHandler(fh)
    
    return logs


logger = log()


def handle_exception(exc_type, exc_value, exc_traceback):
    # ignore traceback to auto close app. except keyboard interrupt
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))


sys.excepthook = handle_exception

app = QApplication(sys.argv)
screen = app.primaryScreen()
size = screen.size()
width = size.width()
height = size.height()

IMG_FORMATS = ['bmp', 'jpg', 'jpeg', 'png', 'tif', 'tiff', 'dng', 'webp', 'mpo']  # acceptable image suffixes
icon = QIcon('./icon/logo2.png')


class MyApp(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle('Easy Boxer')
        self.setWindowIcon(icon)
        self.setGeometry(100, 100, 1600, 900)
        self.setFocusPolicy(Qt.NoFocus)

        # connect QWidget
        self.cent_widget = CentWidget()
        self.setCentralWidget(self.cent_widget.tabs)

        status = self.statusBar()
        status.addPermanentWidget(self.cent_widget.lbl_cnt)

        menubar = self.menuBar()
        menubar.setCornerWidget(QLabel('제작자 : 김찬일   '))
        menu_main = QMenu("메뉴", self)
        menubar.addMenu(menu_main)
        self.action_start = QAction('실행', self)
        self.action_start.setShortcut('F5')
        self.action_start.triggered.connect(self.cent_widget.run)
        self.action_stop = QAction('실행 중지', self)
        self.action_stop.triggered.connect(self.cent_widget.stop)
        menu_main.addAction(self.action_start)
        menu_main.addAction(self.action_stop)
        menu_main.aboutToShow.connect(self.signal)

        self.show()

    def signal(self):
        # enable/disable run thread or stop thread
        if self.cent_widget.show_thread.isRunning():
            self.action_start.setEnabled(False)
            self.action_stop.setEnabled(True)
        else:
            self.action_start.setEnabled(True)
            self.action_stop.setEnabled(False)


class DrawRectangle(QLabel):
    coordinate = pyqtSignal(list)
    resized = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.begin = QPoint(-1, -1)
        self.destination = QPoint(-1, -1)
        self.blue_begin = QPoint(-1, -1)
        self.blue_destination = QPoint(-1, -1)

    def clear_box(self):
        self.begin = QPoint(-1, -1)
        self.destination = QPoint(-1, -1)
        self.blue_begin = QPoint(-1, -1)
        self.blue_destination = QPoint(-1, -1)
        self.update()
        self.coordinate.emit([0, 0, 0, 0])

    def resizeEvent(self, e):
        self.resized.emit()
        self.clear_box()  # if resize then clear box
        return super(DrawRectangle, self).resizeEvent(e)

    def paintEvent(self, e):
        painter = QPainter(self)
        painter.setPen(QPen(Qt.red, 3))  # user draw box
        rect = QRect(self.begin, self.destination)
        painter.drawRect(rect.normalized())
        painter.setPen(QPen(Qt.blue, 3))  # label show box
        painter.drawRect(QRect(self.blue_begin, self.blue_destination))

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.begin = e.pos()
            self.destination = self.begin
            self.update()
        elif e.button() == Qt.RightButton:  # click mouse right button to clear box
            self.begin = QPoint(-1, -1)
            self.destination = QPoint(-1, -1)
            self.update()
            self.coordinate.emit([0, 0, 0, 0])

    def mouseMoveEvent(self, e):  # user draw box
        if e.buttons() == Qt.LeftButton:
            if (e.pos().x() < self.width()) & (e.pos().x() >= 0):
                x = e.pos().x()
            elif e.pos().x() >= self.width():
                x = self.width() - 1
            elif e.pos().x() < 0:
                x = 0
            if (e.pos().y() < self.height()) & (e.pos().y() >= 0):
                y = e.pos().y()
            elif e.pos().y() >= self.height():
                y = self.height() - 1
            elif e.pos().y() < 0:
                y = 0
            self.destination = QPoint(x, y)
            self.update()

    def mouseReleaseEvent(self, e):  # fix box
        if e.button() == Qt.LeftButton:
            coord_list = [self.begin.x(), self.begin.y()]
            if (e.pos().x() < self.width()) & (e.pos().x() >= 0):
                x = e.pos().x()
                coord_list.append(x)
            elif e.pos().x() >= self.width():
                x = self.width() - 1
                coord_list.append(x + 1)
            elif e.pos().x() < 0:
                x = 0
                coord_list.append(x)
            if (e.pos().y() < self.height()) & (e.pos().y() >= 0):
                y = e.pos().y()
                coord_list.append(y)
            elif e.pos().y() >= self.height():
                y = self.height() - 1
                coord_list.append(y + 1)
            elif e.pos().y() < 0:
                y = 0
                coord_list.append(y)
            self.destination = QPoint(x, y)
            self.update()
            self.coordinate.emit(coord_list)


class ShowThread(QThread):
    send_img = pyqtSignal(np.ndarray)
    send_title = pyqtSignal(str)
    send_code = pyqtSignal(str)
    send_cnt = pyqtSignal(str)

    def __init__(self):
        super(ShowThread, self).__init__()
        self.cnt = 0
        self.nf = 0
        self.mutex = QMutex()
        self.cond = QWaitCondition()  # thread control
        self.status = True
        self.img_source = ''
        self.lbl_source = ''
        self.img_path = ''

    def next(self):
        if self.cnt < self.nf - 1:
            self.cnt += 1
        self.status = True
        self.cond.wakeAll()

    def prev(self):
        if self.cnt > 0:
            self.cnt -= 1
        self.status = True
        self.cond.wakeAll()

    def refresh(self):
        self.status = True
        self.cond.wakeAll()

    def move(self, num):
        self.cnt = num
        self.send_cnt.emit(f'{self.cnt + 1}/{self.nf}')
        self.status = True
        self.cond.wakeAll()

    def reset_val(self):
        self.cnt = 0
        self.nf = 0
        self.status = True
        self.img_path = ''

    def run(self):
        p = str(Path(self.img_source).resolve())  # os-agnostic absolute path
        files = sorted(glob(os.path.join(p, '*.*')), key=os.path.getmtime)  # dir
        images = [x for x in files if x.split('.')[-1].lower() in IMG_FORMATS]
        self.nf = len(images)
        while True:
            self.mutex.lock()  # lock thread
            if not self.status:
                self.cond.wait(self.mutex)  # pause thread
            self.img_path = Path(images[self.cnt])
            title = self.img_path.name
            self.send_title.emit(title)
            try:
                img_array = np.fromfile(self.img_path, np.uint8)  # unicode decoding
            except FileNotFoundError:
                img_array = np.fromfile('./icon/error.JPG', np.uint8)
            else:
                logger.info(datetime.fromtimestamp(os.path.getmtime(self.img_path)).strftime('%Y-%m-%d %H:%M:%S'))
            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            self.send_cnt.emit(f'{self.cnt + 1}/{self.nf}')
            fy, fx, _ = img.shape  # height, width, no color
            txt_p = str(Path(self.lbl_source).resolve())  # os-agnostic absolute path
            try:
                with open(txt_p + '\\\\' + self.img_path.stem + '.txt', 'r') as f:  # read txt file
                    code = f.read().strip('\n')
            except FileNotFoundError:
                self.send_code.emit('')
            else:
                self.send_code.emit(code)
                for coordinate in code.split('\n'):  # repeat for more then 1 object
                    try:  # draw rectangle each object
                        _, x, y, w, h = coordinate.split(' ')  # no category
                    except ValueError:
                        pass
                    else:  # CV2 format
                        x = float(x)
                        y = float(y)
                        w = float(w)
                        h = float(h)
                        x1 = round(-fx / 2 * w + fx * x)
                        x2 = round(fx / 2 * w + fx * x)
                        y1 = round(-fy / 2 * h + fy * y)
                        y2 = round(fy / 2 * h + fy * y)
                        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 255), 2)
            img = cv2.resize(img, dsize=(1280, 760), interpolation=cv2.INTER_AREA)
            self.send_img.emit(img)
            self.status = False  # pause
            self.mutex.unlock()  # unlock thread


class CentWidget(QWidget):

    def __init__(self):
        super().__init__()
        self.setWindowIcon(icon)
        self.status = False
        self.bbox = ''  # user draw box coordinate
        self.category = {0:'sample'}
        self.brightness = 0

        self.show_thread = ShowThread()
        self.show_thread.send_img.connect(lambda x: self.show_image(x, self.img, self.brightness))
        self.show_thread.send_title.connect(self.title)
        self.show_thread.send_code.connect(self.code)
        self.show_thread.send_cnt.connect(self.cnt)

        # font
        font = QFont()
        font.setBold(True)
        font.setPointSize(10)

        big_font = QFont()
        big_font.setPointSize(15)
        big_font.setBold(True)

        # color
        color = 'D6F49A'

        # image directory
        self.btn_img = QPushButton('ImageDir', self)
        self.btn_img.setFont(font)
        self.btn_img.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.btn_img.setStatusTip('사진파일 폴더 선택')
        self.btn_img.setToolTip('사진파일 폴더 선택')
        self.btn_img.setStyleSheet(f'background-color: #{color}')
        self.btn_img.clicked.connect(self.img_source)

        # label directory
        self.btn_txt = QPushButton('TextDir', self)
        self.btn_txt.setFont(font)
        self.btn_txt.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.btn_txt.setStatusTip('라벨파일 폴더 선택')
        self.btn_txt.setToolTip('라벨파일 폴더 선택')
        self.btn_txt.setStyleSheet(f'background-color: #{color}')
        self.btn_txt.clicked.connect(self.txt_source)

        # start button
        self.btn_start = QPushButton('START!', self)
        self.btn_start.setFont(font)
        self.btn_start.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.btn_start.setStatusTip('검수 시작')
        self.btn_start.setToolTip('검수 시작')
        self.btn_start.setStyleSheet(f'background-color: #{color}')
        self.btn_start.clicked.connect(self.run)

        # next button
        btn_next = QPushButton('Next', self)
        btn_next.setFont(font)
        btn_next.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        btn_next.setStatusTip('다음 파일로 이동')
        btn_next.setToolTip('다음 파일로 이동')
        btn_next.setStyleSheet(f'background-color: #{color}')
        btn_next.clicked.connect(self.next)

        # prev button
        btn_prev = QPushButton('Prev', self)
        btn_prev.setFont(font)
        btn_prev.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        btn_prev.setStatusTip('이전 파일로 이동')
        btn_prev.setToolTip('이전 파일로 이동')
        btn_prev.setStyleSheet(f'background-color: #{color}')
        btn_prev.clicked.connect(self.prev)

        # add coordinate to txt file
        btn_commit = QPushButton('Add Coordinate', self)
        btn_commit.setFont(font)
        btn_commit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        btn_commit.setStatusTip('좌표를 저장합니다.')
        btn_commit.setToolTip('좌표를 저장합니다.')
        btn_commit.setStyleSheet(f'background-color: #{color}')
        btn_commit.clicked.connect(self.commit)

        # brighten image
        btn_up = QPushButton('brightness', self)
        btn_up.setFont(font)
        btn_up.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        btn_up.setStatusTip('밝기가 증가합니다.')
        btn_up.setToolTip('밝기가 증가합니다.')
        btn_up.setStyleSheet(f'background-color: #{color}')
        btn_up.clicked.connect(self.bright_up)

        # dim image
        btn_down = QPushButton('darkness', self)
        btn_down.setFont(font)
        btn_down.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        btn_down.setStatusTip('밝기가 감소합니다.')
        btn_down.setToolTip('밝기가 감소합니다.')
        btn_down.setStyleSheet(f'background-color: #{color}')
        btn_down.clicked.connect(self.bright_down)

        # edit category
        self.btn_category = QPushButton('Edit Category', self)
        self.btn_category.setFont(font)
        self.btn_category.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.btn_category.setStatusTip('카테고리 변경하기.')
        self.btn_category.setToolTip('카테고리 변경하기')
        self.btn_category.setStyleSheet(f'background-color: #{color}')
        self.btn_category.clicked.connect(self.edit_category)

        # remove image & label file
        btn_rm = QPushButton('사진 제거', self)
        btn_rm.setFont(font)
        btn_rm.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        btn_rm.setStatusTip('해당사진과 라벨파일 모두 제거합니다.')
        btn_rm.setToolTip('해당사진과 라벨파일 모두 제거합니다.')
        btn_rm.setStyleSheet(f'background-color: #{color}')
        btn_rm.clicked.connect(self.erase_file)

        # image directory
        self.lbl_img = QLabel(self)
        self.lbl_img.setFont(font)
        self.lbl_img.setStyleSheet('background-color: #FFFFFF')
        self.lbl_img.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # label directory
        self.lbl_txt = QLabel(self)
        self.lbl_txt.setFont(font)
        self.lbl_txt.setStyleSheet('background-color: #FFFFFF')
        self.lbl_txt.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # brightness
        self.lbl_bright = QLabel('현재밝기 : 0')
        self.lbl_bright.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.lbl_bright.setStatusTip('더블클릭시 밝기를 조절합니다.')
        self.lbl_bright.setToolTip('더블클릭시 밝기를 조절합니다.')
        self.lbl_bright.setAlignment(Qt.AlignCenter)
        self.lbl_bright.mouseDoubleClickEvent = self.bright_chg

        # show image
        self.img = QLabel()
        self.img.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.img.setScaledContents(True)
        self.img.setPixmap(QPixmap('./icon/logo1.png'))

        # image title
        self.lbl_title = QLabel()
        self.lbl_title.setFont(big_font)
        self.lbl_title.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.lbl_title.setStyleSheet('background-color: #FFFFFF')

        # user draw box coordinate
        self.lbl_bbox = QLabel()
        self.lbl_bbox.setFont(big_font)
        self.lbl_bbox.setStyleSheet('background-color: #FFFFFF')

        # file index : Status bar / progress
        self.lbl_cnt = QLabel()
        self.lbl_cnt.setStatusTip('더블클릭시 파일을 이동합니다.')
        self.lbl_cnt.setToolTip('더블클릭시 파일을 이동합니다.')
        self.lbl_cnt.setFixedWidth(80)
        self.lbl_cnt.mouseDoubleClickEvent = self.change

        # show txt file
        self.list_code = QListWidget()
        self.list_code.setFont(big_font)
        self.list_code.setStatusTip('클릭 : 사진에 표시, 더블클릭 : 제거')
        self.list_code.setToolTip('클릭 : 사진에 표시\n더블클릭 : 제거')
        self.list_code.itemClicked.connect(self.blue_square)
        self.list_code.itemDoubleClicked.connect(self.erase_lbl)

        # image bbox palette
        self.lbl_rect = DrawRectangle()
        self.lbl_rect.setAttribute(Qt.WA_TranslucentBackground, True)
        self.lbl_rect.setStatusTip('좌클릭&드래그 : 사진에 표시, 우클릭 : 초기화')
        self.lbl_rect.setToolTip('좌클릭&드래그 : 사진에 표시\n우클릭 : 초기화')
        self.lbl_rect.coordinate.connect(self.coordinate)

        # current category
        self.lbl_category = QLabel('sample')
        self.lbl_category.setStyleSheet('background-color: #FFFFFF')
        self.lbl_category.setFont(big_font)
        self.lbl_category.setAlignment(Qt.AlignCenter)

        # spinbox category
        self.select_category = QSpinBox()
        self.select_category.setMinimum(0)
        self.select_category.setMaximum(len(self.category) - 1)
        self.select_category.valueChanged.connect(self.show_category)

        # layout
        layout = QGridLayout()
        layout.addWidget(self.btn_img, 0, 0, 5, 5)  # 사진경로 지정버튼
        layout.addWidget(self.lbl_img, 0, 5, 5, 60)  # 사진경로 출력라벨
        layout.addWidget(self.btn_txt, 5, 0, 5, 5)  # 라벨경로 지정버튼
        layout.addWidget(self.lbl_txt, 5, 5, 5, 60)  # 라벨경로 출력라벨
        layout.addWidget(self.btn_start, 0, 60, 10, 20)  # 시작 버튼
        layout.addWidget(btn_rm, 10, 60, 10, 20)  # 파일 제거
        layout.addWidget(self.lbl_title, 10, 0, 10, 60)  # 사진 제목
        layout.addWidget(self.img, 20, 0, 80, 80)  # 사진
        layout.addWidget(self.lbl_rect, 20, 0, 80, 80)  # 직사각형그리기
        layout.addWidget(self.lbl_bright, 80, 80, 10, 6)
        layout.addWidget(btn_up, 80, 93, 10, 7)  # 밝기 증가
        layout.addWidget(btn_down, 80, 86, 10, 7)  # 밝기 감소
        layout.addWidget(btn_next, 90, 90, 10, 10)  # 다음 버튼
        layout.addWidget(btn_prev, 90, 80, 10, 10)  # 이전 버튼
        layout.addWidget(btn_commit, 20, 80, 10, 20)  # 커밋 버튼
        layout.addWidget(self.lbl_bbox, 0, 80, 15, 20)  # 직접그린 bbox
        layout.addWidget(self.btn_category, 15, 80, 5, 6)  # 카테고리 버튼
        layout.addWidget(self.lbl_category, 15, 86, 5, 8)  # 카테고리 라벨
        layout.addWidget(self.select_category, 15, 94, 5, 6)  # 카테고리 스핀박스
        layout.addWidget(self.list_code, 30, 80, 50, 20)  # txt bbox

        main = QWidget()
        main.setLayout(layout)

        # tabs
        self.tabs = QTabWidget(self)
        self.tabs.setFocusPolicy(Qt.NoFocus)
        self.tabs.addTab(main, 'Main')

    def erase_lbl(self, e):  # coordinate list double click event to remove coordinate
        if e.text():
            p = str(Path(self.lbl_txt.text()) / Path(self.lbl_title.text()).stem) + '.txt'
            reply = QMessageBox.question(self, '라벨 제거', f"{p}파일에 '{e.text()}'를 제거하시겠습니까?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                with open(p, 'r') as f:
                    s = f.read()
                s = s.replace(e.text(), '').strip('\n').replace('\n\n', '\n')
                with open(p, 'w') as f:
                    f.write(s)
                self.show_thread.refresh()
                self.lbl_rect.clear_box()

    def erase_file(self, e):  # remove image & label at trash
        p_lbl = str(Path(self.lbl_txt.text()) / Path(self.lbl_title.text()).stem) + '.txt'
        p_img = self.show_thread.img_path
        reply = QMessageBox.question(self, '파일 제거', f"다음 파일을 제거하시겠습니까?\n{p_img}\n{p_lbl}",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                send2trash(p_lbl)
            except FileNotFoundError:
                pass
            try:
                send2trash(p_img)
            except FileNotFoundError:
                QMessageBox.warning(self, '파일 찾지 못함', f'파일을 찾지 못했습니다.\n{p_img}')
            finally:
                self.next()

    def blue_square(self, e):  # coordinate list click event to show what it is
        try:
            _, x, y, w, h = e.text().split(' ')  # no category
        except ValueError:
            pass
        else:  # CV2 format
            fx = self.lbl_rect.width()
            fy = self.lbl_rect.height()
            x = float(x)
            y = float(y)
            w = float(w)
            h = float(h)
            x1 = round(-fx / 2 * w + fx * x)
            x2 = round(fx / 2 * w + fx * x)
            y1 = round(-fy / 2 * h + fy * y)
            y2 = round(fy / 2 * h + fy * y)
            self.lbl_rect.blue_begin = QPoint(x1, y1)
            self.lbl_rect.blue_destination = QPoint(x2, y2)
            self.lbl_rect.update()

    def bright_up(self):  # brightly image
        if self.show_thread.isRunning() and self.brightness < 250:
            self.brightness += 25
            self.show_thread.refresh()
            self.lbl_bright.setText(f'현재밝기 : {self.brightness // 25}')

    def bright_down(self):  # dim image
        if self.show_thread.isRunning() and self.brightness > -250:
            self.brightness -= 25
            self.show_thread.refresh()
            self.lbl_bright.setText(f'현재밝기 : {self.brightness // 25}')

    def bright_chg(self, e):  # 현재밝기 double click event to change brightness image
        if self.show_thread.isRunning():
            dlg = QInputDialog(self)
            dlg.setWindowIcon(icon)
            dlg.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint)
            dlg.setInputMode(QInputDialog.IntInput)
            dlg.setWindowTitle('밝기 조절')
            dlg.setLabelText("밝기를 조절합니다.\n-10 부터 10까지")
            dlg.setIntRange(-10, 10)
            dlg.setIntValue(self.brightness // 25)
            ok = dlg.exec_()
            num = dlg.intValue()
            if ok:
                self.brightness = num * 25
                self.show_thread.refresh()
                self.lbl_bright.setText(f'현재밝기 : {num}')

    def run(self):  # run thread
        fname = self.lbl_img.text()
        p = str(Path(str(fname)).resolve())  # os-agnostic absolute path p = \
        files = natsorted(glob(os.path.join(p, '*.*')))  # dir
        images = [x for x in files if x.split('.')[-1].lower() in IMG_FORMATS]
        if not len(images):
            QMessageBox.critical(self, '파일 없음', f'해당 폴더에 사진을 찾지 못했습니다.\n{p}\n지원되는 확장자는:\n'
                                                f'{IMG_FORMATS}', QMessageBox.Ok)
        elif not self.show_thread.isRunning():
            self.show_thread.status = True
            self.btn_start.setEnabled(False)
            self.btn_img.setEnabled(False)
            self.btn_txt.setEnabled(False)
            self.lbl_rect.clear_box()
            self.show_thread.start()
            self.status = True
            try:
                self.lbl_category.setText(self.category[0])
            except (ValueError, KeyError):
                pass

    def stop(self):  # stop thread
        if self.show_thread.isRunning():
            reply = QMessageBox.warning(self, '프로세스 종료', '현재 프로세스를 종료하고 다른 폴더의 파일을 실행하시겠습니까?',
                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.show_thread.status = False
                QTest.qWait(1000)
                self.show_thread.terminate()
                self.img.setPixmap(QPixmap('./icon/logo1.png'))
                self.brightness = 0
                self.lbl_bright = QLabel('현재밝기 : 0')
                self.lbl_rect.clear_box()
                self.list_code.clear()
                self.btn_start.setEnabled(True)
                self.btn_img.setEnabled(True)
                self.btn_txt.setEnabled(True)
                self.lbl_title.clear()
                self.lbl_cnt.clear()
                self.show_thread.reset_val()

    def prev(self):  # button prev click event
        self.show_thread.prev()
        self.lbl_rect.clear_box()

    def next(self):  # button next click event
        self.show_thread.next()
        self.lbl_rect.clear_box()

    def cnt(self, s):  # Status bar / set progress
        self.lbl_cnt.setText(s)

    def change(self, e):  # move file
        if not self.show_thread.status:
            dlg = QInputDialog(self)
            dlg.setWindowIcon(icon)
            dlg.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint)
            dlg.setInputMode(QInputDialog.IntInput)
            dlg.setWindowTitle('파일 이동')
            dlg.setLabelText("원하는 파일로 이동합니다.")
            dlg.resize(500, 100)
            dlg.setIntRange(1, self.show_thread.nf)
            dlg.setIntValue(self.show_thread.cnt + 1)
            ok = dlg.exec_()
            num = dlg.intValue()
            if ok:
                self.show_thread.move(num - 1)

    def commit(self):  # user draw box add to txt file
        if self.status and self.bbox:
            c = str(self.select_category.text()) + ' ' + self.bbox
            p = str(Path(self.lbl_txt.text()) / Path(self.lbl_title.text()).stem) + '.txt'
            category = self.category[self.select_category.value()]
            reply = QMessageBox.question(self, '라벨 추가',
                                         f"{p}파일에 '{c}'를 추가하시겠습니까?\n현재 카테고리 : {category}",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.Yes:
                with open(p, 'a+') as f:
                    f.seek(0)
                    if len(f.read(1)) > 0:
                        f.write('\n')
                    f.write(c)
                self.lbl_rect.clear_box()
                self.show_thread.refresh()

    def code(self, coordinates):  # show label coordinate data
        self.list_code.clear()
        for coordinate in coordinates.split('\n'):
            self.list_code.addItem(coordinate)

    def coordinate(self, coordinate):  # show user draw box coordinate
        x1, y1, x2, y2 = coordinate
        w, h = self.img.width(), self.img.height()
        x = str(round((x1 + x2) / 2 / w, 4))
        y = str(round((y1 + y2) / 2 / h, 4))
        w = str(round(abs(x1 - x2) / w, 4))
        h = str(round(abs(y1 - y2) / h, 4))
        self.lbl_bbox.setText(f'x:{x}\ny:{y}\nw:{w}\nh:{h}')
        self.bbox = ' '.join([x, y, w, h])

    def show_category(self):  # current category
        self.lbl_category.setText(self.category[self.select_category.value()])

    def title(self, title):  # image title (file name)
        self.lbl_title.setText(title)

    def edit_category(self):  # edit category dictionary
        dlg = QInputDialog(self)
        dlg.setWindowIcon(icon)
        dlg.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint)
        dlg.setWindowTitle('Edit Category')
        category = '\n'.join([str(key) + ' / ' + val for key, val in self.category.items()])
        dlg.setLabelText(f'추가할 번호/동물이름을 입력하세요\n예시) 0 / sample\n현재 목록:\n{category}')
        dlg.setTextValue(category.split('\n')[-1])
        ok = dlg.exec_()
        text = dlg.textValue().strip()
        if ok and len(text.split('/')) == 2:
            try:
                key, val = text.split('/')
                key = int(key.strip())
                val = re.sub(r"[^a-zA-Z0-9가-힣_ \-(){}\[\]]", "", val.strip())
            except ValueError:
                QMessageBox.critical(self, '추가 불가', '/앞은 숫자만 가능합니다.')
            else:
                if key > len(self.category):
                    QMessageBox.critical(self, '추가 불가', '비어있는 번호가 생길 수 없습니다.')
                elif key == len(self.category):
                    self.category[key] = val
                    QMessageBox.information(self, '카테고리 추가 완료!',
                                            f"'{key}'의 이름을 '{val}'(으)로 추가하였습니다!")
                    self.select_category.setMaximum(len(self.category) - 1)
                    self.lbl_category.setText(self.category[key])
                else:
                    old_val = self.category[key]
                    self.category[key] = val
                    QMessageBox.information(self, '카테고리 업데이트 완료!',
                                            f"'{key}'의 이름을 '{old_val}'에서 '{val}'(으)로 교체하였습니다!")
                    self.lbl_category.setText(self.category[key])

    def img_source(self):  # glob image list
        if not self.show_thread.isRunning():
            QMessageBox.information(self, '주의사항', '프로그램을 사용하는 도중에 해당 폴더 안의 사진의 이름을 변경하거나 삭제하지 마십시오.')
            fname = QFileDialog.getExistingDirectory(self)  # fname = /
            if fname:
                p = str(Path(str(fname)).resolve())  # os-agnostic absolute path p = \
                files = natsorted(glob(os.path.join(p, '*.*')))  # dir
                images = [x for x in files if x.split('.')[-1].lower() in IMG_FORMATS]
                if not len(images):
                    QMessageBox.critical(self, '파일 없음', f'해당 폴더에 사진을 찾지 못했습니다.\n{p}\n지원되는 확장자는:\n'
                                                        f'{IMG_FORMATS}', QMessageBox.Ok)
                else:
                    self.lbl_img.setText(str(fname))
                    self.show_thread.img_source = str(fname)

    def txt_source(self):  # glob label list
        if not self.show_thread.isRunning():
            fname = QFileDialog.getExistingDirectory(self)  # fname = /
            if fname:
                self.lbl_txt.setText(str(fname))
                self.show_thread.lbl_source = str(fname)

    @staticmethod
    def show_image(img_src, label, val):  # image2pixmap
        try:
            w = label.geometry().width()
            h = label.geometry().height()
            img_src_ = cv2.resize(img_src, (w, h), interpolation=cv2.INTER_AREA)
            frame = cv2.cvtColor(img_src_, cv2.COLOR_BGR2RGB)
            mask = np.full(frame.shape, (val, val, val))
            frame = np.clip(frame + mask, 0, 255).astype(np.uint8)
            img = QImage(frame.data, frame.shape[1], frame.shape[0], frame.shape[2] * frame.shape[1],
                         QImage.Format_RGB888)
            label.setPixmap(QPixmap.fromImage(img))
        except Exception as e:
            logger.warning('show_image error', exc_info=e)


ex = MyApp()
ex.setGeometry(int(0.1 * width), int(0.1 * height), int(0.8 * width), int(0.8 * height))
sys.exit(app.exec_())
