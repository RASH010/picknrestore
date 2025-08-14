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
        # unidad puede ser una letra (str) o una lista de rutas (list)
        self.unidad = unidad
        self.tipo_recuperacion = tipo_recuperacion
        self.cancelado = False

    def run(self):
        try:
            archivos_recuperados = []
            # Si unidad es str (letra), intentamos reparar y escanear la unidad completa.
            if isinstance(self.unidad, str):
                # Reparar sistema de archivos
                self.progreso_actualizado.emit(10, "Reparando sistema de archivos...")
                try:
                    subprocess.run(f'chkdsk {self.unidad}: /f', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                except Exception:
                    pass
                if self.cancelado:
                    return
                # Restablecer atributos
                self.progreso_actualizado.emit(30, "Restableciendo atributos de archivos...")
                try:
                    subprocess.run(f'attrib -h -r -s /s /d {self.unidad}:\\*.*', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                except Exception:
                    pass
                if self.cancelado:
                    return
                rutas_a_escanear = [f"{self.unidad}:\\"]
            else:
                # Si se pasaron rutas (listas), las usamos directamente sin chkdsk
                rutas_a_escanear = list(self.unidad)

            # Buscar archivos recuperables
            self.progreso_actualizado.emit(50, "Buscando archivos recuperables...")
            contador = 0
            for base in rutas_a_escanear:
                for raiz, carpetas, archivos in os.walk(base):
                    for archivo in archivos:
                        if self.cancelado:
                            return
                        ruta_archivo = os.path.join(raiz, archivo)
                        try:
                            if os.path.getsize(ruta_archivo) > 0:
                                archivos_recuperados.append(ruta_archivo)
                                contador += 1
                        except:
                            continue
                        progreso = 50 + int(50 * min(contador, 1000) / 1000)
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
        self.setHeaderLabels(['Archivo', 'Tamaño', 'Fecha Modificación', 'Estado', 'Ruta'])
        self.setColumnWidth(0, 250)
        self.setColumnWidth(4, 400)
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
                    background-color: #3E2723;
                    border: 1px solid #5D4037;
                    font-size: 12px;
                    color: #F7F3F0;
                }
                QTreeWidget::item {
                    padding: 5px;
                }
                QTreeWidget::item:selected {
                    background-color: #6B4C3B;
                    color: white;
                }
                QHeaderView::section {
                    background-color: #6B4C3B;
                    color: white;
                    padding: 5px;
                    border: none;
                }
            """)
        else:
            self.setStyleSheet("""
                QTreeWidget {
                    background-color: #FFFFFF;
                    border: 1px solid #8C6A57;
                    font-size: 12px;
                }
                QTreeWidget::item {
                    color: #6B4C3B;
                    padding: 5px;
                }
                QTreeWidget::item:selected {
                    background-color: #6B4C3B;
                    color: white;
                }
                QHeaderView::section {
                    background-color: #6B4C3B;
                    color: white;
                    padding: 5px;
                    border: none;
                }
            """)
    def agregar_archivos(self, lista_archivos):
        self.clear()
        self.archivos = {}
        # Detectar duplicados por nombre de archivo
        nombre_a_rutas = {}
        for ruta_archivo in lista_archivos:
            nombre = os.path.basename(ruta_archivo)
            nombre_a_rutas.setdefault(nombre, []).append(ruta_archivo)

        # Agrupar por extensión, pero mostrar duplicados como sub-nodos
        for ruta_archivo in lista_archivos:
            ext = os.path.splitext(ruta_archivo)[1].lower()
            if ext not in self.archivos:
                self.archivos[ext] = []
            self.archivos[ext].append(ruta_archivo)

        for ext, archivos in self.archivos.items():
            item_ext = QTreeWidgetItem(self)
            item_ext.setText(0, f"{ext[1:].upper() if ext else 'SIN_EXT'} files ({len(archivos)})")
            item_ext.setIcon(0, self.obtener_icono(ext))
            item_ext.setData(0, Qt.UserRole, ext)
            item_ext.setFlags(item_ext.flags() | Qt.ItemIsTristate | Qt.ItemIsUserCheckable)
            item_ext.setCheckState(0, Qt.Unchecked)

            # Crear mapa de nombre->rutas dentro de esta extensión para orden
            nombres_en_ext = {}
            for ruta in archivos:
                nombre = os.path.basename(ruta)
                nombres_en_ext.setdefault(nombre, []).append(ruta)

            for nombre, rutas in nombres_en_ext.items():
                if len(rutas) > 1:
                    # Nodo agrupador para duplicados del mismo nombre
                    item_nombre = QTreeWidgetItem(item_ext)
                    item_nombre.setText(0, f"{nombre} (Duplicado x{len(rutas)})")
                    item_nombre.setIcon(0, self.obtener_icono(ext))
                    item_nombre.setFlags(item_nombre.flags() | Qt.ItemIsTristate | Qt.ItemIsUserCheckable)
                    item_nombre.setCheckState(0, Qt.Unchecked)
                    for ruta_unica in rutas:
                        try:
                            tamaño = self.formato_tamano(os.path.getsize(ruta_unica))
                            fecha = self.formato_fecha(os.path.getmtime(ruta_unica))
                        except Exception:
                            tamaño = "-"
                            fecha = "-"
                        hijo = QTreeWidgetItem(item_nombre)
                        hijo.setText(0, nombre)
                        hijo.setText(1, tamaño)
                        hijo.setText(2, fecha)
                        hijo.setText(3, "Duplicado")
                        hijo.setText(4, ruta_unica)
                        hijo.setIcon(0, self.obtener_icono(ext))
                        hijo.setData(0, Qt.UserRole, ruta_unica)
                        hijo.setFlags(hijo.flags() | Qt.ItemIsUserCheckable)
                        hijo.setCheckState(0, Qt.Unchecked)
                else:
                    ruta_unica = rutas[0]
                    try:
                        tamaño = self.formato_tamano(os.path.getsize(ruta_unica))
                        fecha = self.formato_fecha(os.path.getmtime(ruta_unica))
                    except Exception:
                        tamaño = "-"
                        fecha = "-"
                    item_archivo = QTreeWidgetItem(item_ext)
                    item_archivo.setText(0, nombre)
                    item_archivo.setText(1, tamaño)
                    item_archivo.setText(2, fecha)
                    item_archivo.setText(3, "Backup")
                    item_archivo.setText(4, ruta_unica)
                    item_archivo.setIcon(0, self.obtener_icono(ext))
                    item_archivo.setData(0, Qt.UserRole, ruta_unica)
                    item_archivo.setFlags(item_archivo.flags() | Qt.ItemIsUserCheckable)
                    item_archivo.setCheckState(0, Qt.Unchecked)
            item_ext.setExpanded(True)

        # Conectar señal para manejar cambios de checkbox y mantener coherencia
        self.itemChanged.connect(self._on_item_changed)
    def obtener_icono(self, extension):
        return self.iconos_archivo.get(extension, self.iconos_archivo['default'])

    def _on_item_changed(self, item, column):
        # Cuando cambia el estado de un item, propagamos a hijos/padres implícitamente
        # Qt.ItemIsTristate ayuda, pero manejamos coherencia adicional si es necesario.
        # No hacemos nada pesado aquí.
        pass
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

    def obtener_rutas_marcadas(self):
        """Devuelve la lista de rutas (strings) de los files marcados (checkbox).
        Solo devuelve rutas que correspondan a archivos (hojas con UserRole).
        """
        rutas = []
        def recorrer(item):
            for i in range(item.childCount()):
                hijo = item.child(i)
                # Si tiene hijos, recorrer recursivamente
                if hijo.childCount() > 0:
                    recorrer(hijo)
                else:
                    ruta = hijo.data(0, Qt.UserRole)
                    if ruta and hijo.checkState(0) == Qt.Checked:
                        rutas.append(ruta)
        # Revisar top-level
        for idx in range(self.topLevelItemCount()):
            top = self.topLevelItem(idx)
            recorrer(top)
        return rutas

    def marcar_todo(self, marcar=True):
        estado = Qt.Checked if marcar else Qt.Unchecked
        self.blockSignals(True)
        for i in range(self.topLevelItemCount()):
            top = self.topLevelItem(i)
            top.setCheckState(0, estado)
            for j in range(top.childCount()):
                child = top.child(j)
                child.setCheckState(0, estado)
                for k in range(child.childCount()):
                    grand = child.child(k)
                    grand.setCheckState(0, estado)
        self.blockSignals(False)

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
                    stop:0 #8C6A57, stop:1 #3E2723);
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
    def __init__(self):
        super().__init__()
        self.dark_mode = False
        self._carpetas_seleccionadas = []
        self.trabajador_recuperacion = None

        self.setWindowTitle("Pick & Restore")
        self.setGeometry(100, 100, 900, 600)
        self.configurar_ui()
        self.configurar_iconos()

    def cambiar_tema(self, valor):
        self.dark_mode = bool(valor)
        self.apply_theme()
        self.update_styles()
        if hasattr(self, 'selector_tema'):
            self.selector_tema.slider.setValue(int(self.dark_mode))

    def configurar_iconos(self):
        try:
            self.boton_escanear.setIcon(QIcon(resource_path('icons/icono_scan.png')))
            self.boton_cancelar.setIcon(QIcon(resource_path('icons/icono_cancelar.png')))
            self.boton_exportar.setIcon(QIcon(resource_path('icons/icono_exportar.png')))
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
            print(f"Error cargando iconos: {e}")

    def configurar_ui(self):
        self.apply_theme()

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Barra superior
        top_bar = QHBoxLayout()

        unit_controls = QHBoxLayout()
        unit_controls.setSpacing(8)

        self.combo_unidades = QComboBox()
        self.combo_unidades.setFixedWidth(150)
        self.actualizar_unidades()

        self.boton_escanear = QPushButton(" Escanear Unidad")
        self.boton_escanear.clicked.connect(self.iniciar_recuperacion)

        self.boton_cancelar = QPushButton(" Cancelar")
        self.boton_cancelar.clicked.connect(self.cancelar_recuperacion)
        self.boton_cancelar.setEnabled(False)

        unit_controls.addWidget(QLabel("Unidad:"))
        unit_controls.addWidget(self.combo_unidades)
        unit_controls.addWidget(self.boton_escanear)
        unit_controls.addWidget(self.boton_cancelar)

        # Selección manual de carpetas
        self.boton_seleccionar_carpetas = QPushButton(" Seleccionar Carpetas")
        self.boton_seleccionar_carpetas.clicked.connect(self.seleccionar_carpetas)
        unit_controls.addWidget(self.boton_seleccionar_carpetas)

        # Barra de progreso y tema
        self.barra_progreso = QProgressBar()
        self.barra_progreso.setFixedHeight(20)
        self.barra_progreso.setTextVisible(False)

        self.selector_tema = ThemeSlider()
        self.selector_tema.slider.valueChanged.connect(self.cambiar_tema)

        self.etiqueta_estado = QLabel("Seleccione una unidad o carpetas y haga clic en Escanear")

        top_bar.addLayout(unit_controls)
        top_bar.addWidget(self.barra_progreso)
        top_bar.addWidget(self.selector_tema)
        top_bar.addWidget(self.etiqueta_estado, stretch=1)

        # Área principal
        splitter = QSplitter(Qt.Vertical)
        self.gestor_archivos = GestorArchivos(self.dark_mode)

        # Controles de selección
        seleccion_bar = QHBoxLayout()
        self.boton_marcar_todo = QPushButton("Marcar/Desmarcar Todo")
        self.boton_marcar_todo.clicked.connect(self._toggle_marcar_todo)
        seleccion_bar.addWidget(self.boton_marcar_todo)
        seleccion_bar.addStretch()

        # Barra inferior
        bottom_bar = QHBoxLayout()
        self.boton_exportar = QPushButton(" Exportar Selección")
        self.boton_exportar.clicked.connect(self.exportar_archivos)
        self.boton_exportar.setEnabled(False)
        bottom_bar.addWidget(self.boton_exportar)
        bottom_bar.addStretch()

        splitter.addWidget(self.gestor_archivos)

        main_layout.addLayout(top_bar)
        main_layout.addLayout(seleccion_bar)
        main_layout.addWidget(splitter)
        main_layout.addLayout(bottom_bar)

        # Conectar señales
        self.gestor_archivos.itemSelectionChanged.connect(self.actualizar_boton_exportar)
        self.gestor_archivos.itemChanged.connect(self.actualizar_boton_exportar)

        self.update_styles()

    def apply_theme(self):
        palette = QPalette()
        if self.dark_mode:
            palette.setColor(QPalette.Window, QColor(30, 30, 30))
            palette.setColor(QPalette.WindowText, QColor(220, 220, 220))
            palette.setColor(QPalette.Base, QColor(50, 50, 50))
        else:
            palette.setColor(QPalette.Window, QColor(240, 245, 250))
            palette.setColor(QPalette.WindowText, QColor(30, 63, 102))
        self.setPalette(palette)

    def update_styles(self):
        # Simplificado: aplicamos estilos básicos y estilos a botones
        # Aplicar estilos más completos para asegurar contraste
        if self.dark_mode:
            palette_css = """
                QMainWindow { background-color: #3E2723; }
                QLabel { color: #F7F3F0; }
                QComboBox { background: #5D4037; color: #F7F3F0; border: 1px solid #8C6A57; padding: 5px; border-radius: 4px; }
                QComboBox QAbstractItemView { background: #5D4037; color: #F7F3F0; selection-background-color: #6B4C3B; }
                QProgressBar { border: 1px solid #5D4037; background: #5D4037; color: #F7F3F0; }
                QSplitter::handle { background: #5D4037; }
            """
            btn_style = "background-color: #6B4C3B; color: white;"
            cancel_style = "background-color: #D9534F; color: white;"
            export_style = "background-color: #8F6F5B; color: white;"
        else:
            palette_css = """
                QMainWindow { background-color: #FFFFFF; }
                QLabel { color: #6B4C3B; }
                QComboBox { background: #FFFFFF; color: #6B4C3B; border: 1px solid #8C6A57; padding: 5px; border-radius: 4px; }
                QComboBox QAbstractItemView { background: #FFFFFF; color: #6B4C3B; selection-background-color: #EDE0D8; }
                QProgressBar { border: 1px solid #8C6A57; background: #FFFFFF; color: #6B4C3B; }
                QSplitter::handle { background: #8C6A57; }
            """
            btn_style = "background-color: #6B4C3B; color: white;"
            cancel_style = "background-color: #D9534F; color: white;"
            export_style = "background-color: #8F6F5B; color: white;"

        # Aplicar hoja de estilo general
        self.setStyleSheet(palette_css)

        # Estilos específicos de botones
        self.boton_escanear.setStyleSheet(btn_style)
        self.boton_cancelar.setStyleSheet(cancel_style)
        self.boton_exportar.setStyleSheet(export_style)

        # Actualizar tema del gestor de archivos
        self.gestor_archivos.modo_oscuro = self.dark_mode
        self.gestor_archivos.actualizar_tema()

        # Asegurar que los QMessageBox también sean legibles en ambos modos
        try:
            app = QApplication.instance()
            if app:
                if self.dark_mode:
                    msgbox_css = """
                        QMessageBox {
                            background-color: #3E2723; 
                            color: #F7F3F0;
                        }
                        QMessageBox QLabel { color: #F7F3F0; }
                        QMessageBox QPushButton { background-color: #6B4C3B; color: #F7F3F0; border: none; padding: 5px 10px; border-radius: 4px; }
                        QMessageBox QPushButton:hover { background-color: #8C6A57; }
                    """
                else:
                    msgbox_css = """
                        QMessageBox { background-color: #FFFFFF; color: #6B4C3B; }
                        QMessageBox QLabel { color: #6B4C3B; }
                        QMessageBox QPushButton { background-color: #6B4C3B; color: white; border: none; padding: 5px 10px; border-radius: 4px; }
                        QMessageBox QPushButton:hover { background-color: #8C6A57; }
                    """
                # Aplicar solo las reglas de QMessageBox a nivel de aplicación
                # (no sobreescribe estilos locales del main window)
                app.setStyleSheet(msgbox_css)
        except Exception:
            pass

    def actualizar_unidades(self):
        self.combo_unidades.clear()
        for particion in psutil.disk_partitions():
            if 'removable' in particion.opts or 'fixed' in particion.opts:
                unidad = particion.device[0]
                self.combo_unidades.addItem(f"{unidad}: {particion.mountpoint}", unidad)

    def iniciar_recuperacion(self, usando_carpetas=False):
        # Determinar objetivo: unidad o carpetas
        if usando_carpetas and getattr(self, '_carpetas_seleccionadas', None):
            rutas = self._carpetas_seleccionadas
            usar_carpetas = True
        else:
            unidad = self.combo_unidades.currentData()
            usar_carpetas = False
            if not unidad:
                QMessageBox.warning(self, "Error", "Seleccione una unidad válida")
                return

        # Confirmación
        if usar_carpetas:
            lista_texto = "\n".join(rutas[:5]) + ("..." if len(rutas) > 5 else "")
            respuesta = QMessageBox.question(self, 'Confirmación', f'¿Está seguro de escanear las siguientes carpetas?\n{lista_texto}\n\nEsta operación puede tomar varios minutos.', QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            argumento = rutas
        else:
            respuesta = QMessageBox.question(self, 'Confirmación', f'¿Está seguro de realizar la recuperación en la unidad {unidad}:?\n\nEsta operación puede tomar varios minutos.', QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            argumento = unidad

        if respuesta != QMessageBox.Yes:
            if hasattr(self, '_carpetas_seleccionadas'):
                del self._carpetas_seleccionadas
            return

        # Deshabilitar controles
        self.boton_escanear.setEnabled(False)
        self.combo_unidades.setEnabled(False)
        self.boton_cancelar.setEnabled(True)
        self.boton_exportar.setEnabled(False)
        self.barra_progreso.setValue(0)

        # Iniciar hilo
        self.trabajador_recuperacion = TrabajadorRecuperacion(argumento, "rapida")
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

    def seleccionar_carpetas(self):
        ruta = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta (OK para añadir)")
        if not ruta:
            return
        carpetas = [ruta]
        añadir = QMessageBox.question(self, 'Añadir más', '¿Desea añadir otra carpeta a escanear?', QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        while añadir == QMessageBox.Yes:
            ruta_extra = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta adicional")
            if ruta_extra:
                carpetas.append(ruta_extra)
            añadir = QMessageBox.question(self, 'Añadir más', '¿Desea añadir otra carpeta a escanear?', QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        self._carpetas_seleccionadas = carpetas
        self.iniciar_recuperacion(usando_carpetas=True)

    def _toggle_marcar_todo(self):
        marcados = self.gestor_archivos.obtener_rutas_marcadas()
        if len(marcados) == 0:
            self.gestor_archivos.marcar_todo(True)
        else:
            self.gestor_archivos.marcar_todo(False)

    def recuperacion_finalizada(self, lista_archivos):
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
        # Habilitar si hay selección visible o checkboxes marcados
        seleccionado = len(self.gestor_archivos.selectedItems()) > 0
        marcados = len(self.gestor_archivos.obtener_rutas_marcadas()) > 0
        self.boton_exportar.setEnabled(seleccionado or marcados)

    def exportar_archivos(self):
        rutas_marcadas = self.gestor_archivos.obtener_rutas_marcadas()
        if len(rutas_marcadas) == 0:
            seleccionados = self.gestor_archivos.selectedItems()
            rutas = [it.data(0, Qt.UserRole) for it in seleccionados if it.data(0, Qt.UserRole)]
        else:
            rutas = rutas_marcadas

        if not rutas:
            QMessageBox.information(self, "Exportar", "No hay archivos seleccionados para exportar")
            return

        carpeta_destino = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta destino")
        if not carpeta_destino:
            return

        exitos = 0
        errores = 0
        common_prefix = os.path.commonpath(rutas)
        for ruta_archivo in rutas:
            if not os.path.isfile(ruta_archivo):
                continue
            try:
                try:
                    relativa = os.path.relpath(ruta_archivo, common_prefix)
                except Exception:
                    relativa = os.path.basename(ruta_archivo)
                destino_full = os.path.join(carpeta_destino, relativa)
                destino_dir = os.path.dirname(destino_full)
                os.makedirs(destino_dir, exist_ok=True)
                final_path = destino_full
                contador = 1
                while os.path.exists(final_path):
                    nombre, ext = os.path.splitext(destino_full)
                    final_path = f"{nombre}_dup{contador}{ext}"
                    contador += 1
                shutil.copy2(ruta_archivo, final_path)
                exitos += 1
            except Exception as e:
                errores += 1
                print(f"Error exportando {ruta_archivo}: {e}")

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
                    background-color: #6B4C3B;
            color: white;
            border: none;
            padding: 5px 10px;
            border-radius: 4px;
            min-width: 80px;
        }
        QMessageBox QPushButton:hover {
            background-color: #8C6A57;
        }
    """)
    ventana = VentanaPrincipal()
    ventana.show()
    sys.exit(app.exec_())