import os
import sys
import subprocess
import psutil
import shutil
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QTreeWidget, QTreeWidgetItem, QLabel, QComboBox,
                             QProgressBar, QFileDialog, QMessageBox, QSplitter, QHeaderView,
                             QSlider, QFrame, QSizePolicy)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QIcon, QPalette, QColor

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS  # Para PyInstaller
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))  # Directorio donde está este script
    return os.path.join(base_path, relative_path)



class TrabajadorRecuperacion(QThread):
    progreso_actualizado = pyqtSignal(int, str)
    recuperacion_completada = pyqtSignal(list)
    error_ocurrido = pyqtSignal(str)

    def __init__(self, unidad, tipo_recuperacion):
        super().__init__()
        self.unidad = unidad
        self.tipo_recuperacion = tipo_recuperacion
        self.cancelado = False

    def run(self):
        try:
            archivos_recuperados = []
            # Reparar sistema de archivos
            self.progreso_actualizado.emit(10, "Reparando sistema de archivos...")
            subprocess.run(f'chkdsk {self.unidad}: /f', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if self.cancelado:
                return
            # Restablecer atributos
            self.progreso_actualizado.emit(30, "Restableciendo atributos de archivos...")
            subprocess.run(f'attrib -h -r -s /s /d {self.unidad}:\\*.*', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if self.cancelado:
                return
            # Buscar archivos recuperables
            self.progreso_actualizado.emit(50, "Buscando archivos recuperables...")
            for raiz, carpetas, archivos in os.walk(f"{self.unidad}:\\"):
                for archivo in archivos:
                    if self.cancelado:
                        return
                    ruta_archivo = os.path.join(raiz, archivo)
                    try:
                        if os.path.getsize(ruta_archivo) > 0:
                            archivos_recuperados.append(ruta_archivo)
                    except:
                        continue
                    progreso = 50 + int(50 * len(archivos_recuperados) / 1000)
                    self.progreso_actualizado.emit(min(progreso, 99), f"Encontrados {len(archivos_recuperados)} archivos")
            self.progreso_actualizado.emit(100, "Recuperación completada")
            self.recuperacion_completada.emit(archivos_recuperados)
        except Exception as e:
            self.error_ocurrido.emit(str(e))

    def cancelar(self):
        self.cancelado = True

class GestorArchivos(QTreeWidget):
    def __init__(self, modo_oscuro=False):
        super().__init__()
        self.modo_oscuro = modo_oscuro
        self.configurar_ui()
        self.archivos = {}
    def configurar_ui(self):
        self.setHeaderLabels(['Archivo', 'Tamaño', 'Fecha Modificación', 'Estado'])
        self.setColumnWidth(0, 250)
        self.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.setSelectionMode(QTreeWidget.ExtendedSelection)
        # Iconos por defecto (serán reemplazados en MainWindow)
        self.iconos_archivo = {
            '.txt': QIcon(),
            '.pdf': QIcon(),
            '.jpg': QIcon(),
            '.png': QIcon(),
            '.docx': QIcon(),
            '.xlsx': QIcon(),
            'default': QIcon()
        }
        self.actualizar_tema()
    def actualizar_tema(self):
        if self.modo_oscuro:
            self.setStyleSheet("""
                QTreeWidget {
                    background-color: #121212;
                    border: 1px solid #444;
                    font-size: 12px;
                    color: #E0E0E0;
                }
                QTreeWidget::item {
                    padding: 5px;
                }
                QTreeWidget::item:selected {
                    background-color: #1E3F66;
                    color: white;
                }
                QHeaderView::section {
                    background-color: #1E3F66;
                    color: white;
                    padding: 5px;
                    border: none;
                }
            """)
        else:
            self.setStyleSheet("""
                QTreeWidget {
                    background-color: #FFFFFF;
                    border: 1px solid #1E3F66;
                    font-size: 12px;
                }
                QTreeWidget::item {
                    color: #1E3F66;
                    padding: 5px;
                }
                QTreeWidget::item:selected {
                    background-color: #1E3F66;
                    color: white;
                }
                QHeaderView::section {
                    background-color: #1E3F66;
                    color: white;
                    padding: 5px;
                    border: none;
                }
            """)
    def agregar_archivos(self, lista_archivos):
        self.clear()
        self.archivos = {}
        for ruta_archivo in lista_archivos:
            ext = os.path.splitext(ruta_archivo)[1].lower()
            if ext not in self.archivos:
                self.archivos[ext] = []
            self.archivos[ext].append(ruta_archivo)
        for ext, archivos in self.archivos.items():
            item_ext = QTreeWidgetItem(self)
            item_ext.setText(0, f"{ext[1:].upper()} files ({len(archivos)})")
            item_ext.setIcon(0, self.obtener_icono(ext))
            item_ext.setData(0, Qt.UserRole, ext)
            for ruta_archivo in archivos:
                nombre_archivo = os.path.basename(ruta_archivo)
                item_archivo = QTreeWidgetItem(item_ext)
                item_archivo.setText(0, nombre_archivo)
                item_archivo.setText(1, self.formato_tamano(os.path.getsize(ruta_archivo)))
                item_archivo.setText(2, self.formato_fecha(os.path.getmtime(ruta_archivo)))
                item_archivo.setText(3, "Backup")
                item_archivo.setIcon(0, self.obtener_icono(ext))
                item_archivo.setData(0, Qt.UserRole, ruta_archivo)
            item_ext.setExpanded(True)
    def obtener_icono(self, extension):
        return self.iconos_archivo.get(extension, self.iconos_archivo['default'])
    @staticmethod
    def formato_tamano(tamano_bytes):
        for unidad in ['B', 'KB', 'MB', 'GB']:
            if tamano_bytes < 1024.0:
                return f"{tamano_bytes:.2f} {unidad}"
            tamano_bytes /= 1024.0
        return f"{tamano_bytes:.2f} TB"
    @staticmethod
    def formato_fecha(timestamp):
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

class ThemeSlider(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        self.light_label = QLabel("☀️")
        self.dark_label = QLabel("🌙")
        
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(1)
        self.slider.setFixedWidth(50)
        self.slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 5px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1E3F66, stop:1 #121212);
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                width: 15px;
                height: 15px;
                background: white;
                border: 1px solid #777;
                border-radius: 7px;
                margin: -5px 0;
            }
        """)
        
        layout.addWidget(self.light_label)
        layout.addWidget(self.slider)
        layout.addWidget(self.dark_label)
        self.setLayout(layout)

class VentanaPrincipal(QMainWindow):
    def cambiar_tema(self, valor):
        """
        Cambia entre modo claro y oscuro según el valor del slider.
        """
        self.dark_mode = bool(valor)
        self.apply_theme()
        self.update_styles()
        self.selector_tema.slider.setValue(int(self.dark_mode))
    def __init__(self):
        super().__init__()
        self.dark_mode = False
        self.setWindowTitle("Pick & Restore")
        self.setGeometry(100, 100, 900, 600)
        self.configurar_ui()
        self.configurar_iconos()
        self.trabajador_recuperacion = None

    def configurar_iconos(self):
        """Configura todos los iconos de la aplicación"""
        try:
            # Iconos para botones
            self.boton_escanear.setIcon(QIcon(resource_path('icons/icono_scan.png')))
            self.boton_escanear.setIconSize(QSize(24, 24))
            self.boton_cancelar.setIcon(QIcon(resource_path('icons/icono_cancelar.png')))
            self.boton_cancelar.setIconSize(QSize(24, 24))
            self.boton_exportar.setIcon(QIcon(resource_path('icons/icono_exportar.png')))
            self.boton_exportar.setIconSize(QSize(24, 24))
            self.gestor_archivos.iconos_archivo = {
                '.txt': QIcon(resource_path('icons/icono_txt.png')),
                '.pdf': QIcon(resource_path('icons/icono_pdf.png')),
                '.jpg': QIcon(resource_path('icons/icono_jpg.png')),
                '.png': QIcon(resource_path('icons/icono_png.png')),
                '.docx': QIcon(resource_path('icons/icono_docx.png')),
                '.xlsx': QIcon(resource_path('icons/icono_xlsx.png')),
                'default': QIcon(resource_path('icons/icono_default.png'))
            }
        except Exception as e:
            print(f"Error cargando iconos: {str(e)}")
            self.boton_escanear.setIcon(QIcon.fromTheme('system-search'))
            self.boton_cancelar.setIcon(QIcon.fromTheme('dialog-cancel'))
            self.boton_exportar.setIcon(QIcon.fromTheme('document-save-as'))

    def configurar_ui(self):
        self.apply_theme()
        
        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Barra superior - Controles
        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)
        
        # Controles de unidad
        unit_controls = QHBoxLayout()
        unit_controls.setSpacing(10)
        
        self.combo_unidades = QComboBox()
        self.combo_unidades.setFixedWidth(150)
        self.actualizar_unidades()
        self.boton_escanear = QPushButton(" Escanear Unidad")
        self.boton_escanear.setIconSize(QSize(24, 24))
        self.boton_escanear.clicked.connect(self.iniciar_recuperacion)
        self.boton_cancelar = QPushButton(" Cancelar")
        self.boton_cancelar.setIconSize(QSize(24, 24))
        self.boton_cancelar.clicked.connect(self.cancelar_recuperacion)
        self.boton_cancelar.setEnabled(False)
        unit_controls.addWidget(QLabel("Unidad:"))
        unit_controls.addWidget(self.combo_unidades)
        unit_controls.addWidget(self.boton_escanear)
        unit_controls.addWidget(self.boton_cancelar)
        
        # Barra de progreso
        self.barra_progreso = QProgressBar()
        self.barra_progreso.setFixedHeight(20)
        self.barra_progreso.setTextVisible(False)
        
        # Selector de tema
        self.selector_tema = ThemeSlider()
        self.selector_tema.slider.valueChanged.connect(self.cambiar_tema)
        
        # Barra de estado
        self.etiqueta_estado = QLabel("Seleccione una unidad y haga clic en Escanear")
        
        # Organizar barra superior
        top_bar.addLayout(unit_controls)
        top_bar.addWidget(self.barra_progreso)
        top_bar.addWidget(self.selector_tema)
        top_bar.addWidget(self.etiqueta_estado, stretch=1)
        
        # Área principal
        splitter = QSplitter(Qt.Vertical)
        
        # Lista de archivos
        self.gestor_archivos = GestorArchivos(self.dark_mode)
        
        # Barra inferior - Exportación
        bottom_bar = QHBoxLayout()
        self.boton_exportar = QPushButton(" Exportar Selección")
        self.boton_exportar.setIconSize(QSize(24, 24))
        self.boton_exportar.clicked.connect(self.exportar_archivos)
        self.boton_exportar.setEnabled(False)
        bottom_bar.addWidget(self.boton_exportar)
        bottom_bar.addStretch()
        
        # Diseño completo
        splitter.addWidget(self.gestor_archivos)
        
        main_layout.addLayout(top_bar)
        main_layout.addWidget(splitter)
        main_layout.addLayout(bottom_bar)
        
        # Conectar señales
        self.gestor_archivos.itemSelectionChanged.connect(self.actualizar_boton_exportar)
        self.update_styles()

    def apply_theme(self):
        palette = QPalette()
        if self.dark_mode:
            # Tema oscuro
            palette.setColor(QPalette.Window, QColor(30, 30, 30))
            palette.setColor(QPalette.WindowText, QColor(220, 220, 220))
            palette.setColor(QPalette.Base, QColor(50, 50, 50))
            palette.setColor(QPalette.AlternateBase, QColor(60, 60, 60))
            palette.setColor(QPalette.ToolTipBase, QColor(30, 63, 102))
            palette.setColor(QPalette.ToolTipText, Qt.white)
            palette.setColor(QPalette.Text, QColor(220, 220, 220))
            palette.setColor(QPalette.Button, QColor(50, 50, 50))
            palette.setColor(QPalette.ButtonText, QColor(220, 220, 220))
            palette.setColor(QPalette.BrightText, Qt.red)
            palette.setColor(QPalette.Highlight, QColor(44, 83, 130))
            palette.setColor(QPalette.HighlightedText, Qt.white)
        else:
            # Tema claro
            palette.setColor(QPalette.Window, QColor(240, 245, 250))
            palette.setColor(QPalette.WindowText, QColor(30, 63, 102))
            palette.setColor(QPalette.Base, QColor(255, 255, 255))
            palette.setColor(QPalette.AlternateBase, QColor(240, 245, 250))
            palette.setColor(QPalette.ToolTipBase, QColor(30, 63, 102))
            palette.setColor(QPalette.ToolTipText, Qt.white)
            palette.setColor(QPalette.Text, QColor(30, 63, 102))
            palette.setColor(QPalette.Button, QColor(30, 63, 102))
            palette.setColor(QPalette.ButtonText, Qt.white)
            palette.setColor(QPalette.BrightText, Qt.red)
            palette.setColor(QPalette.Highlight, QColor(44, 83, 130))
            palette.setColor(QPalette.HighlightedText, Qt.white)
        
        self.setPalette(palette)

    def update_styles(self):
        if self.dark_mode:
            # Estilos para tema oscuro
            self.setStyleSheet("""
                QMainWindow {
                    background-color: #1E1E1E;
                }
                QComboBox {
                    background: #333;
                    color: #EEE;
                    border: 1px solid #444;
                    padding: 5px;
                    border-radius: 4px;
                }
                QComboBox QAbstractItemView {
                    background: #333;
                    color: #EEE;
                    selection-background-color: #1E3F66;
                }
                QLabel {
                    color: #DDD;
                }
                QProgressBar {
                    border: 1px solid #444;
                    border-radius: 4px;
                    text-align: center;
                    background: #333;
                }
                QProgressBar::chunk {
                    background-color: #1E3F66;
                }
                QSplitter::handle {
                    background: #444;
                }
            """)
            
            btn_style = """
                QPushButton {
                    background-color: #1E3F66;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #2C5382;
                }
                QPushButton:disabled {
                    background-color: #95A5A6;
                }
            """
            
            cancel_btn_style = """
                QPushButton {
                    background-color: #D9534F;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #C9302C;
                }
                QPushButton:disabled {
                    background-color: #95A5A6;
                }
            """
            
            export_btn_style = """
                QPushButton {
                    background-color: #5CB85C;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #4CAE4C;
                }
                QPushButton:disabled {
                    background-color: #95A5A6;
                }
            """
        else:
            # Estilos para tema claro
            self.setStyleSheet("""
                QMainWindow {
                    background-color: #F0F5FA;
                }
                QComboBox {
                    background: white;
                    border: 1px solid #1E3F66;
                    padding: 5px;
                    border-radius: 4px;
                }
                QLabel {
                    color: #1E3F66;
                }
                QProgressBar {
                    border: 1px solid #1E3F66;
                    border-radius: 4px;
                    text-align: center;
                }
                QProgressBar::chunk {
                    background-color: #1E3F66;
                }
                QSplitter::handle {
                    background: #1E3F66;
                }
            """)
            
            btn_style = """
                QPushButton {
                    background-color: #1E3F66;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #2C5382;
                }
                QPushButton:disabled {
                    background-color: #95A5A6;
                }
            """
            
            cancel_btn_style = """
                QPushButton {
                    background-color: #D9534F;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #C9302C;
                }
                QPushButton:disabled {
                    background-color: #95A5A6;
                }
            """
            
            export_btn_style = """
                QPushButton {
                    background-color: #5CB85C;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #4CAE4C;
                }
                QPushButton:disabled {
                    background-color: #95A5A6;
                }
            """
        
        # Aplicar estilos a los botones
        self.boton_escanear.setStyleSheet(btn_style)
        self.boton_cancelar.setStyleSheet(cancel_btn_style)
        self.boton_exportar.setStyleSheet(export_btn_style)

        # Actualizar tema del gestor de archivos
        self.gestor_archivos.modo_oscuro = self.dark_mode
        self.gestor_archivos.actualizar_tema()

        # Actualizar estilo de la etiqueta de estado
        if self.dark_mode:
            self.etiqueta_estado.setStyleSheet("""
                QLabel {
                    color: #DDD;
                    font-style: italic;
                    padding: 5px;
                }
            """)
        else:
            self.etiqueta_estado.setStyleSheet("""
                QLabel {
                    color: #1E3F66;
                    font-style: italic;
                    padding: 5px;
                }
            """)

    def toggle_theme(self, value):
        self.dark_mode = bool(value)
        self.apply_theme()
        self.update_styles()
        self.selector_tema.slider.setValue(int(self.dark_mode))

    def actualizar_unidades(self):
        """
        Lee todas las unidades disponibles en el sistema (discos duros, USB, etc.)
        usando psutil.disk_partitions().
        Agrega al comboBox (self.drive_combo) cada unidad encontrada, mostrando la letra y el punto de montaje.
        Esto permite al usuario seleccionar la unidad donde se realizará la recuperación.
        """
        self.combo_unidades.clear()
        for particion in psutil.disk_partitions():
            if 'removable' in particion.opts or 'fixed' in particion.opts:
                unidad = particion.device[0]
                self.combo_unidades.addItem(f"{unidad}: {particion.mountpoint}", unidad)

    def iniciar_recuperacion(self):
        """
        Inicia el proceso de recuperación en la unidad seleccionada.
        1. Obtiene la letra de la unidad seleccionada en el comboBox.
        2. Pide confirmación al usuario.
        3. Deshabilita los controles mientras se ejecuta la recuperación.
        4. Crea un hilo (RecoveryWorker) que:
           - Ejecuta chkdsk y attrib para reparar y desbloquear archivos.
           - Recorre toda la unidad usando os.walk para encontrar archivos recuperables.
           - Por cada archivo encontrado, lo agrega a una lista si tiene tamaño > 0.
           - Emite señales de progreso y resultado.
        """
        unidad = self.combo_unidades.currentData()
        if not unidad:
            QMessageBox.warning(self, "Error", "Seleccione una unidad válida")
            return
        respuesta = QMessageBox.question(
            self,
            'Confirmación',
            f'¿Está seguro de realizar la recuperación en la unidad {unidad}:?\n\nEsta operación puede tomar varios minutos.',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if respuesta != QMessageBox.Yes:
            return
        self.boton_escanear.setEnabled(False)
        self.combo_unidades.setEnabled(False)
        self.boton_cancelar.setEnabled(True)
        self.boton_exportar.setEnabled(False)
        self.barra_progreso.setValue(0)
        # Lanzar hilo de recuperación
        self.trabajador_recuperacion = TrabajadorRecuperacion(unidad, "rapida")
        self.trabajador_recuperacion.progreso_actualizado.connect(self.actualizar_progreso)
        self.trabajador_recuperacion.recuperacion_completada.connect(self.recuperacion_finalizada)
        self.trabajador_recuperacion.error_ocurrido.connect(self.error_recuperacion)
        self.trabajador_recuperacion.start()

    def cancelar_recuperacion(self):
        if self.trabajador_recuperacion and self.trabajador_recuperacion.isRunning():
            self.trabajador_recuperacion.cancelar()
            self.etiqueta_estado.setText("Recuperación cancelada por el usuario")
            self.barra_progreso.setValue(0)
        self.boton_escanear.setEnabled(True)
        self.combo_unidades.setEnabled(True)
        self.boton_cancelar.setEnabled(False)

    def actualizar_progreso(self, valor, mensaje):
        self.barra_progreso.setValue(valor)
        self.etiqueta_estado.setText(mensaje)

    def recuperacion_finalizada(self, lista_archivos):
        """
        Cuando termina la recuperación, se recibe la lista de archivos encontrados.
        Se llama a self.gestor_archivos.agregar_archivos(lista_archivos), que:
        - Agrupa los archivos por extensión.
        - Para cada archivo, obtiene su nombre, tamaño y fecha de modificación.
        - Los muestra en el QTreeWidget, permitiendo al usuario seleccionar cuáles exportar.
        """
        self.gestor_archivos.agregar_archivos(lista_archivos)
        self.etiqueta_estado.setText(f"Recuperación completada: {len(lista_archivos)} archivos encontrados")
        self.barra_progreso.setValue(100)
        self.boton_escanear.setEnabled(True)
        self.combo_unidades.setEnabled(True)
        self.boton_cancelar.setEnabled(False)
        self.boton_exportar.setEnabled(len(lista_archivos) > 0)

    def error_recuperacion(self, mensaje_error):
        QMessageBox.critical(self, "Error", f"Ocurrió un error durante la recuperación:\n{mensaje_error}")
        self.etiqueta_estado.setText("Error durante la recuperación")
        self.barra_progreso.setValue(0)
        self.boton_escanear.setEnabled(True)
        self.combo_unidades.setEnabled(True)
        self.boton_cancelar.setEnabled(False)

    def actualizar_boton_exportar(self):
        seleccionado = len(self.gestor_archivos.selectedItems()) > 0
        self.boton_exportar.setEnabled(seleccionado)

    def exportar_archivos(self):
        """
        Exporta (copia) los archivos seleccionados por el usuario a una carpeta destino.
        1. Obtiene los archivos seleccionados en el QTreeWidget.
        2. Pide al usuario seleccionar la carpeta destino.
        3. Por cada archivo seleccionado:
           - Copia el archivo a la carpeta destino usando shutil.copy2.
           - Si ocurre un error, lo cuenta y lo muestra en consola.
        4. Muestra un mensaje con el resultado de la exportación.
        """
        seleccionados = self.gestor_archivos.selectedItems()
        if not seleccionados:
            return
        carpeta_destino = QFileDialog.getExistingDirectory(
            self,
            "Seleccionar carpeta destino"
        )
        if not carpeta_destino:
            return
        exitos = 0
        errores = 0
        for item in seleccionados:
            ruta_archivo = item.data(0, Qt.UserRole)
            if os.path.isfile(ruta_archivo):
                try:
                    destino = os.path.join(carpeta_destino, os.path.basename(ruta_archivo))
                    shutil.copy2(ruta_archivo, destino)
                    exitos += 1
                except Exception as e:
                    errores += 1
                    print(f"Error exportando {ruta_archivo}: {str(e)}")
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("Exportación completada")
        msg.setText(f"Se exportaron {exitos} archivos correctamente")
        if errores > 0:
            msg.setInformativeText(f"{errores} archivos no pudieron exportarse (ver consola para detalles)")
        msg.exec_()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    # Configurar estilos para QMessageBox
    app.setStyleSheet("""
        QMessageBox {
            background-color: palette(window);
        }
        QMessageBox QLabel {
            color: palette(window-text);
        }
        QMessageBox QPushButton {
            background-color: #1E3F66;
            color: white;
            border: none;
            padding: 5px 10px;
            border-radius: 4px;
            min-width: 80px;
        }
        QMessageBox QPushButton:hover {
            background-color: #2C5382;
        }
    """)
    ventana = VentanaPrincipal()
    ventana.show()
    sys.exit(app.exec_())