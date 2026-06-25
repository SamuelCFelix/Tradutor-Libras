import sys
import os
import threading
import io
import wave

import sounddevice as sd
import numpy as np
import speech_recognition as sr

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QPushButton, QTextEdit, QSplitter, QFrame,
)
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings, QWebEngineProfile
from PyQt5.QtCore import Qt, QUrl, pyqtSignal, QObject, QTimer
from PyQt5.QtGui import QFont

SAMPLE_RATE = 16000
CHANNELS = 1
HTML_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vlibras.html")


class Sinais(QObject):
    texto_pronto = pyqtSignal(str)
    status_mudou = pyqtSignal(str, str)


class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tradutor Libras")
        self.setMinimumSize(960, 750)
        self.resize(1100, 820)

        self.recording = False
        self.frames = []
        self.recognizer = sr.Recognizer()

        self.sinais = Sinais()
        self.sinais.texto_pronto.connect(self._on_texto)
        self.sinais.status_mudou.connect(self._on_status)

        self._build_ui()

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._barra_status())

        splitter = QSplitter(Qt.Vertical)
        splitter.setHandleWidth(4)
        splitter.setStyleSheet("QSplitter::handle { background: #2a2a4a; }")
        splitter.addWidget(self._painel_vlibras())
        splitter.addWidget(self._painel_texto())
        splitter.setSizes([650, 130])

        root.addWidget(splitter)

    def _barra_status(self):
        frame = QFrame()
        frame.setFixedHeight(46)
        frame.setStyleSheet("background: #12121f; border-bottom: 1px solid #2a2a4a;")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(14, 0, 14, 0)

        self.indicador = QLabel("●")
        self.indicador.setFont(QFont("Segoe UI", 15))
        self.indicador.setStyleSheet("color: #444466;")

        self.status_label = QLabel("Carregando VLibras...")
        self.status_label.setFont(QFont("Segoe UI", 12))
        self.status_label.setStyleSheet("color: #666688; margin-left: 6px;")

        btn = QPushButton("Limpar")
        btn.setFont(QFont("Segoe UI", 11))
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                background: #2a2a4a; color: #aaaacc;
                border: none; padding: 5px 16px; border-radius: 5px;
            }
            QPushButton:hover { background: #3a3a6a; color: white; }
        """)
        btn.clicked.connect(self._limpar)

        layout.addWidget(self.indicador)
        layout.addWidget(self.status_label)
        layout.addStretch()
        layout.addWidget(btn)
        return frame

    def _painel_vlibras(self):
        profile = QWebEngineProfile.defaultProfile()
        profile.setHttpUserAgent(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )

        self.webview = QWebEngineView()
        s = self.webview.settings()
        s.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        s.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        s.setAttribute(QWebEngineSettings.AllowRunningInsecureContent, True)
        s.setAttribute(QWebEngineSettings.WebGLEnabled, True)
        s.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)
        s.setAttribute(QWebEngineSettings.FullScreenSupportEnabled, True)
        s.setAttribute(QWebEngineSettings.PluginsEnabled, True)
        self.webview.load(QUrl.fromLocalFile(HTML_PATH))
        return self.webview

    def _painel_texto(self):
        frame = QFrame()
        frame.setStyleSheet("background: #0e0e1c;")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 8, 14, 10)
        layout.setSpacing(4)

        titulo = QLabel("TEXTO TRANSCRITO")
        titulo.setStyleSheet("color: #44446a; font-size: 10px; letter-spacing: 1px;")
        layout.addWidget(titulo)

        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        self.text_area.setFont(QFont("Segoe UI", 13))
        self.text_area.setStyleSheet("""
            QTextEdit {
                background: #0e0e1c; color: #d0d0ff;
                border: none; selection-background-color: #3a3a7a;
            }
        """)
        layout.addWidget(self.text_area)
        return frame

    # --------------------------------------------------------- Teclado

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space and not event.isAutoRepeat():
            self._iniciar_gravacao()
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Space and not event.isAutoRepeat():
            self._parar_gravacao()
        else:
            super().keyReleaseEvent(event)

    # --------------------------------------------------------- Gravação

    def _iniciar_gravacao(self):
        if self.recording:
            return
        self.recording = True
        self.frames = []
        self.text_area.clear()
        self.sinais.status_mudou.emit("Gravando...  (solte ESPAÇO para transcrever)", "#ff4444")
        threading.Thread(target=self._gravar, daemon=True).start()

    def _gravar(self):
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="int16") as stream:
            while self.recording:
                data, _ = stream.read(1024)
                self.frames.append(data.copy())

    def _parar_gravacao(self):
        if not self.recording:
            return
        self.recording = False
        self.sinais.status_mudou.emit("Transcrevendo...", "#ffaa00")
        threading.Thread(target=self._transcrever, daemon=True).start()

    def _transcrever(self):
        if not self.frames:
            self.sinais.status_mudou.emit("Segure  ESPAÇO  para falar", "#888888")
            return

        audio_np = np.concatenate(self.frames, axis=0)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio_np.tobytes())
        buf.seek(0)

        try:
            with sr.AudioFile(buf) as source:
                audio = self.recognizer.record(source)
            texto = self.recognizer.recognize_google(audio, language="pt-BR")
            self.sinais.texto_pronto.emit(texto)
        except sr.UnknownValueError:
            self.sinais.status_mudou.emit("Não entendi — tente novamente", "#ff6633")
            QTimer.singleShot(2000, lambda: self.sinais.status_mudou.emit(
                "Segure  ESPAÇO  para falar", "#888888"))
        except sr.RequestError as e:
            self.sinais.status_mudou.emit(f"Erro de rede: {e}", "#ff3333")
            QTimer.singleShot(2000, lambda: self.sinais.status_mudou.emit(
                "Segure  ESPAÇO  para falar", "#888888"))

    # --------------------------------------------------------- Callbacks

    def _on_texto(self, texto):
        self.text_area.setPlainText(texto)

        texto_safe = texto.replace("\\", "\\\\").replace("'", "\\'").replace("\n", " ")
        self.webview.page().runJavaScript(f"traduzir('{texto_safe}')")

    def _on_status(self, mensagem, cor):
        self.status_label.setText(mensagem)
        self.status_label.setStyleSheet(f"color: {cor}; margin-left: 6px;")
        self.indicador.setStyleSheet(
            f"color: {cor};" if cor != "#888888" else "color: #444466;"
        )

    def _limpar(self):
        self.text_area.clear()


# ------------------------------------------------------------------ Main

if __name__ == "__main__":
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = App()
    window.show()

    sys.exit(app.exec_())
