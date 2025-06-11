import sys
import os
import subprocess
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QFileDialog, QLabel,
    QVBoxLayout, QWidget, QHBoxLayout, QSlider, QMessageBox
)
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtCore import QUrl, Qt, QEvent, QObject, QPoint
from PySide6.QtGui import QMouseEvent, QPixmap


class ClickableSlider(QSlider):
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.setMouseTracking(True)
        self.thumbnails = []
        self.video_duration = 0

        self.preview_label = QLabel(parent)
        self.preview_label.setWindowFlags(Qt.ToolTip)
        self.preview_label.setFixedSize(160, 90)
        self.preview_label.setStyleSheet("""
            background-color: rgba(0, 0, 0, 180);
            border: 1px solid #2c7be5;
            border-radius: 4px;
        """)
        self.preview_label.hide()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            x = event.position().x()
            ratio = x / self.width()
            new_val = round(ratio * (self.maximum() - self.minimum()) + self.minimum())
            self.setValue(new_val)
            self.sliderMoved.emit(new_val)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.thumbnails and self.video_duration > 0:
            x = event.position().x()
            ratio = x / self.width()
            ratio = max(0.0, min(1.0, ratio))
            index = int(ratio * (len(self.thumbnails) - 1))

            thumb_path = self.thumbnails[index]
            if os.path.exists(thumb_path):
                pixmap = QPixmap(thumb_path).scaled(160, 90, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.preview_label.setPixmap(pixmap)

                global_pos = self.mapToGlobal(event.position().toPoint())
                x_offset = -self.preview_label.width() // 2
                y_offset = -self.preview_label.height() - 10
                pos = QPoint(global_pos.x() + x_offset, global_pos.y() + y_offset)
                self.preview_label.move(pos)
                self.preview_label.show()
        else:
            self.preview_label.hide()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self.preview_label.hide()
        super().leaveEvent(event)


class ClickableVideoWidget(QVideoWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.mediaPlayer = None
        self.setStyleSheet("background-color: #111111; border-radius: 8px;")

    def mousePressEvent(self, event: QMouseEvent):
        if self.mediaPlayer:
            if self.mediaPlayer.playbackState() == QMediaPlayer.PlayingState:
                self.mediaPlayer.pause()
            else:
                self.mediaPlayer.play()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Video Kırpma Uygulaması")
        self.resize(1000, 750)
        self.setFocusPolicy(Qt.StrongFocus)  # Burada pencerenin klavye eventlerini almasını sağlıyoruz

        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
                color: #333333;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                font-size: 12pt;
            }
            QPushButton {
                background-color: #2c7be5;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #1a5fcc;
            }
            QPushButton:checked {
                background-color: #1a5fcc;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #ddd;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #2c7be5;
                border: none;
                width: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }
            QSlider::handle:horizontal:hover {
                background: #1a5fcc;
            }
            QLabel {
                color: #444444;
                font-weight: normal;
            }
            QLabel#positionLabel {
                font-size: 10pt;
                color: #555555;
            }
            QLabel#speedLabel {
                font-weight: bold;
                color: #2c7be5;
            }
        """)

        self.mediaPlayer = QMediaPlayer()
        self.audioOutput = QAudioOutput()
        self.mediaPlayer.setAudioOutput(self.audioOutput)
        self.playbackRate = 1.0

        self.videoWidget = ClickableVideoWidget()
        self.videoWidget.mediaPlayer = self.mediaPlayer

        self.selectButton = QPushButton("Video Seç")
        self.selectButton.clicked.connect(self.open_file_dialog)

        self.playPauseButton = QPushButton("Oynat")
        self.playPauseButton.clicked.connect(self.toggle_play_pause)

        self.forwardButton = QPushButton(">> 5 sn")
        self.forwardButton.clicked.connect(self.forward_video)

        self.backwardButton = QPushButton("<< 5 sn")
        self.backwardButton.clicked.connect(self.backward_video)

        self.volumeSlider = QSlider(Qt.Horizontal)
        self.volumeSlider.setRange(0, 100)
        self.volumeSlider.setValue(50)
        self.volumeSlider.valueChanged.connect(self.change_volume)

        self.positionSlider = ClickableSlider(Qt.Horizontal, self)
        self.positionSlider.setRange(0, 0)
        self.positionSlider.sliderMoved.connect(self.set_position)

        self.positionLabel = QLabel("00:00 / 00:00")
        self.positionLabel.setObjectName("positionLabel")

        self.speedLabel = QLabel(f"Hız: {self.playbackRate:.1f}x")
        self.speedLabel.setObjectName("speedLabel")

        self.speedUpButton = QPushButton("Hızlandır (+)")
        self.speedUpButton.clicked.connect(self.increase_speed)
        self.slowDownButton = QPushButton("Yavaşlat (-)")
        self.slowDownButton.clicked.connect(self.decrease_speed)

        self.fullscreenButton = QPushButton("Tam Ekran")
        self.fullscreenButton.setCheckable(True)
        self.fullscreenButton.clicked.connect(self.toggle_fullscreen)

        # Tema butonu eklendi
        self.themeButton = QPushButton("Karanlık Tema")
        self.themeButton.setCheckable(True)
        self.themeButton.clicked.connect(self.toggle_theme)

        # --- YENİ: Kesme butonları ve durum göstergeleri
        self.trimStartButton = QPushButton("Başlangıç Noktasını Seç")
        self.trimStartButton.clicked.connect(self.set_trim_start)
        self.trimEndButton = QPushButton("Bitiş Noktasını Seç")
        self.trimEndButton.clicked.connect(self.set_trim_end)
        self.trimButton = QPushButton("Kes ve Kaydet")
        self.trimButton.clicked.connect(self.trim_and_save)
        self.trimButton.setEnabled(False)

        self.trimStartLabel = QLabel("Başlangıç: --:--")
        self.trimEndLabel = QLabel("Bitiş: --:--")

        trimLayout = QHBoxLayout()
        trimLayout.addWidget(self.trimStartButton)
        trimLayout.addWidget(self.trimEndButton)
        trimLayout.addWidget(self.trimButton)
        trimLayout.addWidget(self.trimStartLabel)
        trimLayout.addWidget(self.trimEndLabel)

        controlLayout = QHBoxLayout()
        controlLayout.addWidget(self.playPauseButton)
        controlLayout.addWidget(self.backwardButton)
        controlLayout.addWidget(self.forwardButton)
        controlLayout.addWidget(QLabel("Ses:"))
        controlLayout.addWidget(self.volumeSlider)
        controlLayout.addWidget(self.slowDownButton)
        controlLayout.addWidget(self.speedUpButton)
        controlLayout.addWidget(self.speedLabel)
        controlLayout.addWidget(self.fullscreenButton)
        controlLayout.addWidget(self.themeButton)

        layout = QVBoxLayout()
        layout.addWidget(self.videoWidget, stretch=3)
        layout.addWidget(self.positionSlider)
        layout.addWidget(self.positionLabel)
        layout.addWidget(self.selectButton)
        layout.addLayout(controlLayout)
        layout.addLayout(trimLayout)  # --- YENİ: trim layout

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.mediaPlayer.setVideoOutput(self.videoWidget)
        self.mediaPlayer.positionChanged.connect(self.position_changed)
        self.mediaPlayer.durationChanged.connect(self.duration_changed)

        self.video_path = ""
        self.thumbnail_count = 10

        # --- YENİ: Trim başlangıç ve bitiş süreleri (ms)
        self.trim_start = None
        self.trim_end = None

    def open_file_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Video Dosyası Seç", "", "Video Dosyaları (*.mp4 *.avi *.mov)")
        if file_path:
            self.video_path = file_path
            self.mediaPlayer.setSource(QUrl.fromLocalFile(file_path))
            self.mediaPlayer.play()
            self.playPauseButton.setText("Duraklat")

    def create_thumbnails(self):
        # Hata kontrolleri
        if not self.video_path or not os.path.exists(self.video_path):
            return
        # Thumbnail klasörü
        thumb_dir = os.path.join(os.path.dirname(self.video_path), ".thumbnails")
        if not os.path.exists(thumb_dir):
            os.makedirs(thumb_dir)
        # Mevcutları temizle
        for f in os.listdir(thumb_dir):
            if f.endswith(".jpg"):
                try:
                    os.remove(os.path.join(thumb_dir, f))
                except Exception:
                    pass

        self.positionSlider.thumbnails.clear()

        # Süre saniye cinsinden
        duration_ms = self.mediaPlayer.duration()
        if duration_ms <= 0:
            return
        duration_s = duration_ms / 1000

        step = duration_s / self.thumbnail_count

        for i in range(self.thumbnail_count):
            thumb_time = i * step
            thumb_path = os.path.join(thumb_dir, f"thumb_{i}.jpg")

            # ffmpeg ile thumbnail oluştur
            cmd = [
                "ffmpeg",
                "-ss", str(thumb_time),
                "-i", self.video_path,
                "-frames:v", "1",
                "-q:v", "2",
                "-y",
                thumb_path
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.positionSlider.thumbnails.append(thumb_path)

        self.positionSlider.video_duration = duration_ms

    def toggle_play_pause(self):
        if self.mediaPlayer.playbackState() == QMediaPlayer.PlayingState:
            self.mediaPlayer.pause()
            self.playPauseButton.setText("Oynat")
        else:
            self.mediaPlayer.play()
            self.playPauseButton.setText("Duraklat")

    def forward_video(self):
        pos = self.mediaPlayer.position()
        self.mediaPlayer.setPosition(min(pos + 5000, self.mediaPlayer.duration()))

    def backward_video(self):
        pos = self.mediaPlayer.position()
        self.mediaPlayer.setPosition(max(pos - 5000, 0))

    def change_volume(self, value):
        self.audioOutput.setVolume(value / 100)

    def set_position(self, position):
        self.mediaPlayer.setPosition(position)

    def position_changed(self, position):
        duration = self.mediaPlayer.duration()
        self.positionSlider.blockSignals(True)
        self.positionSlider.setValue(position)
        self.positionSlider.blockSignals(False)
        self.positionLabel.setText(f"{self.ms_to_hhmmss(position)} / {self.ms_to_hhmmss(duration)}")

    def duration_changed(self, duration):
        self.positionSlider.setRange(0, duration)
        self.create_thumbnails()

    def increase_speed(self):
        self.playbackRate = min(self.playbackRate + 0.1, 4.0)
        self.mediaPlayer.setPlaybackRate(self.playbackRate)
        self.speedLabel.setText(f"Hız: {self.playbackRate:.1f}x")

    def decrease_speed(self):
        self.playbackRate = max(self.playbackRate - 0.1, 0.1)
        self.mediaPlayer.setPlaybackRate(self.playbackRate)
        self.speedLabel.setText(f"Hız: {self.playbackRate:.1f}x")

    def toggle_fullscreen(self, checked):
        if checked:
            self.showFullScreen()
            self.fullscreenButton.setText("Pencere Modu")
        else:
            self.showNormal()
            self.fullscreenButton.setText("Tam Ekran")

    def toggle_theme(self, checked):
        if checked:
            # Karanlık tema
            self.setStyleSheet("""
                QMainWindow { background-color: #121212; color: #f0f0f0; }
                QPushButton { background-color: #3700b3; color: #ffffff; }
                QPushButton:hover { background-color: #6200ee; }
                QSlider::groove:horizontal { background: #444444; }
                QSlider::handle:horizontal { background: #bb86fc; }
                QLabel { color: #bbbbbb; }
            """)
            self.themeButton.setText("Açık Tema")
        else:
            # Açık tema (default)
            self.setStyleSheet("""
                QMainWindow {
                    background-color: #f5f5f5;
                    color: #333333;
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    font-size: 12pt;
                }
                QPushButton {
                    background-color: #2c7be5;
                    color: white;
                    border: none;
                    padding: 6px 12px;
                    border-radius: 4px;
                    min-width: 80px;
                }
                QPushButton:hover {
                    background-color: #1a5fcc;
                }
                QPushButton:checked {
                    background-color: #1a5fcc;
                }
                QSlider::groove:horizontal {
                    height: 6px;
                    background: #ddd;
                    border-radius: 3px;
                }
                QSlider::handle:horizontal {
                    background: #2c7be5;
                    border: none;
                    width: 14px;
                    margin: -5px 0;
                    border-radius: 7px;
                }
                QSlider::handle:horizontal:hover {
                    background: #1a5fcc;
                }
                QLabel {
                    color: #444444;
                    font-weight: normal;
                }
                QLabel#positionLabel {
                    font-size: 10pt;
                    color: #555555;
                }
                QLabel#speedLabel {
                    font-weight: bold;
                    color: #2c7be5;
                }
            """)
            self.themeButton.setText("Karanlık Tema")

    def ms_to_hhmmss(self, ms):
        seconds = ms // 1000
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        else:
            return f"{m:02d}:{s:02d}"

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Space:
            self.toggle_play_pause()
        elif key == Qt.Key_Right:
            self.forward_video()
        elif key == Qt.Key_Left:
            self.backward_video()
        elif key == Qt.Key_Plus or key == Qt.Key_Equal:
            self.increase_speed()
        elif key == Qt.Key_Minus:
            self.decrease_speed()
        elif key == Qt.Key_Escape and self.isFullScreen():
            self.fullscreenButton.setChecked(False)
            self.toggle_fullscreen(False)
        else:
            super().keyPressEvent(event)

    # --- YENİ: Trim noktalarını ayarlayan fonksiyonlar
    def set_trim_start(self):
        pos = self.mediaPlayer.position()
        if pos >= (self.trim_end if self.trim_end is not None else self.mediaPlayer.duration()):
            QMessageBox.warning(self, "Hata", "Başlangıç noktası bitiş noktasından önce olmalı.")
            return
        self.trim_start = pos
        self.trimStartLabel.setText(f"Başlangıç: {self.ms_to_hhmmss(pos)}")
        self.trimButton.setEnabled(self.trim_start is not None and self.trim_end is not None)

    def set_trim_end(self):
        pos = self.mediaPlayer.position()
        if pos <= (self.trim_start if self.trim_start is not None else 0):
            QMessageBox.warning(self, "Hata", "Bitiş noktası başlangıç noktasından sonra olmalı.")
            return
        self.trim_end = pos
        self.trimEndLabel.setText(f"Bitiş: {self.ms_to_hhmmss(pos)}")
        self.trimButton.setEnabled(self.trim_start is not None and self.trim_end is not None)

    def trim_and_save(self):
        if not self.video_path or self.trim_start is None or self.trim_end is None:
            QMessageBox.warning(self, "Hata", "Lütfen başlangıç ve bitiş noktalarını seçin.")
            return
        if self.trim_start >= self.trim_end:
            QMessageBox.warning(self, "Hata", "Başlangıç noktası bitiş noktasından önce olmalı.")
            return

        save_path, _ = QFileDialog.getSaveFileName(self, "Kesilen Videoyu Kaydet", "", "MP4 Video (*.mp4);;Tüm Dosyalar (*)")
        if not save_path:
            return

        start_sec = self.trim_start / 1000.0
        duration_sec = (self.trim_end - self.trim_start) / 1000.0

        # ffmpeg komutu oluştur
        cmd = [
            "ffmpeg",
            "-y",
            "-i", self.video_path,
            "-ss", f"{start_sec:.3f}",
            "-t", f"{duration_sec:.3f}",
            "-c", "copy",  # Yeniden kodlamadan kesme yapar
            save_path
        ]

        # ffmpeg çalıştır
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if result.returncode == 0:
            QMessageBox.information(self, "Başarılı", "Video başarıyla kesildi ve kaydedildi.")
        else:
            QMessageBox.critical(self, "Hata", f"Kesme işlemi başarısız oldu.\n\n{result.stderr.decode()}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
