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

SILENCE_THRESHOLD = 500
SILENCE_CHUNKS = 24


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

        self.modo_ao_vivo = False
        self._stop_ao_vivo = False

        self.sinais = Sinais()
        self.sinais.texto_pronto.connect(self._on_texto)
        self.sinais.status_mudou.connect(self._on_status)

        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._barra_status())

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(4)
        splitter.setStyleSheet("QSplitter::handle { background: #2a2a4a; }")
        splitter.addWidget(self._painel_texto())
        splitter.addWidget(self._painel_vlibras())
        splitter.setSizes([550, 550])

        root.addWidget(splitter)

        self.webview.loadFinished.connect(self._on_webview_carregado)

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

        self.btn_modo = QPushButton("Ao vivo")
        self.btn_modo.setFont(QFont("Segoe UI", 11))
        self.btn_modo.setCursor(Qt.PointingHandCursor)
        self._estilo_btn_inativo = """
            QPushButton {
                background: #2a2a4a; color: #aaaacc;
                border: none; padding: 5px 16px; border-radius: 5px;
            }
            QPushButton:hover { background: #3a3a6a; color: white; }
        """
        self._estilo_btn_ativo = """
            QPushButton {
                background: #6a1a1a; color: #ffaaaa;
                border: none; padding: 5px 16px; border-radius: 5px;
            }
            QPushButton:hover { background: #8a2a2a; color: white; }
        """
        self.btn_modo.setStyleSheet(self._estilo_btn_inativo)
        self.btn_modo.clicked.connect(self._toggle_ao_vivo)

        layout.addWidget(self.indicador)
        layout.addWidget(self.status_label)
        layout.addStretch()
        layout.addWidget(self.btn_modo)
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
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)

        titulo = QLabel("TEXTO TRANSCRITO")
        titulo.setStyleSheet("color: #44446a; font-size: 10px; letter-spacing: 1px;")
        layout.addWidget(titulo)

        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        self.text_area.setFont(QFont("Segoe UI", 15))
        self.text_area.setStyleSheet("""
            QTextEdit {
                background: #0e0e1c; color: #d0d0ff;
                border: none; selection-background-color: #3a3a7a;
            }
        """)
        layout.addWidget(self.text_area)
        return frame

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space and not event.isAutoRepeat() and not self.modo_ao_vivo:
            self._iniciar_gravacao()
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Space and not event.isAutoRepeat() and not self.modo_ao_vivo:
            self._parar_gravacao()
        else:
            super().keyReleaseEvent(event)

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

    def _transcrever(self, frames=None):
        dados = frames if frames is not None else self.frames
        if not dados:
            self.sinais.status_mudou.emit("Segure  ESPAÇO  para falar", "#888888")
            return

        audio_np = np.concatenate(dados, axis=0)
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
            if not self.modo_ao_vivo:
                self.sinais.status_mudou.emit("Não entendi — tente novamente", "#ff6633")
                QTimer.singleShot(2000, lambda: self.sinais.status_mudou.emit(
                    "Segure  ESPAÇO  para falar", "#888888"))
        except sr.RequestError as e:
            self.sinais.status_mudou.emit(f"Erro de rede: {e}", "#ff3333")
            QTimer.singleShot(2000, lambda: self.sinais.status_mudou.emit(
                "Segure  ESPAÇO  para falar", "#888888"))

    def _toggle_ao_vivo(self):
        if self.modo_ao_vivo:
            self._parar_ao_vivo()
        else:
            self._iniciar_ao_vivo()

    def _iniciar_ao_vivo(self):
        if self.recording:
            return
        self.modo_ao_vivo = True
        self._stop_ao_vivo = False
        self.btn_modo.setText("Parar ao vivo")
        self.btn_modo.setStyleSheet(self._estilo_btn_ativo)
        self.sinais.status_mudou.emit("Ao vivo — ouvindo...", "#ff6600")
        threading.Thread(target=self._loop_ao_vivo, daemon=True).start()

    def _parar_ao_vivo(self):
        self._stop_ao_vivo = True
        self.modo_ao_vivo = False
        self.btn_modo.setText("Ao vivo")
        self.btn_modo.setStyleSheet(self._estilo_btn_inativo)
        self.sinais.status_mudou.emit("Segure  ESPAÇO  para falar", "#888888")

    def _loop_ao_vivo(self):
        frames_fala = []
        chunks_silencio = 0
        falando = False

        with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="int16") as stream:
            while not self._stop_ao_vivo:
                data, _ = stream.read(1024)
                rms = float(np.sqrt(np.mean(data.astype(np.float32) ** 2)))

                if rms > SILENCE_THRESHOLD:
                    frames_fala.append(data.copy())
                    chunks_silencio = 0
                    if not falando:
                        falando = True
                        self.sinais.status_mudou.emit("Ao vivo — captando fala...", "#ff4444")
                elif falando:
                    frames_fala.append(data.copy())
                    chunks_silencio += 1
                    if chunks_silencio >= SILENCE_CHUNKS:

                        self.sinais.status_mudou.emit("Ao vivo — traduzindo...", "#ffaa00")
                        segmento = frames_fala.copy()
                        frames_fala = []
                        chunks_silencio = 0
                        falando = False
                        threading.Thread(
                            target=self._transcrever,
                            args=(segmento,),
                            daemon=True,
                        ).start()
                        self.sinais.status_mudou.emit("Ao vivo — ouvindo...", "#ff6600")


    def _on_webview_carregado(self, _ok):

        QTimer.singleShot(4000, lambda: self.sinais.status_mudou.emit(
            "Segure  ESPAÇO  para falar", "#0066FF"
        ))

    def _on_texto(self, texto):
        if self.modo_ao_vivo:
            self.text_area.append(texto)
        else:
            self.text_area.setPlainText(texto)
        texto_safe = texto.replace("\\", "\\\\").replace("'", "\\'").replace("\n", " ")
        self.webview.page().runJavaScript(f"traduzir('{texto_safe}')")

    def _on_status(self, mensagem, cor):
        self.status_label.setText(mensagem)
        self.status_label.setStyleSheet(f"color: {cor}; margin-left: 6px;")
        self.indicador.setStyleSheet(
            f"color: {cor};" if cor != "#888888" else "color: #444466;"
        )


if __name__ == "__main__":
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = App()
    window.show()

    sys.exit(app.exec_())
