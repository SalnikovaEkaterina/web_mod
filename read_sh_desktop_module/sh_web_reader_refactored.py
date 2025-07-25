import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from PyQt5 import QtWidgets, QtCore, QtGui
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar

from ui_form_sh_web_reader import Ui_ShWebReaderForm


class CheckboxTableMixin:
    """Миксин для управления цветом и состоянием чекбоксов"""

    def __init__(self):
        self.checkbox_states = {}

    def init_checkbox_behavior(self):
        """Инициализация поведения чекбоксов (должна вызываться после создания UI)"""
        if not hasattr(self, 'ui'):
            return

        table = self.ui.tableWidget_sh_web_params
        table.horizontalHeader().sectionClicked.connect(self.on_header_clicked)
        table.itemChanged.connect(self.update_item_color)
        table.itemChanged.connect(self.on_well_checkbox_changed)

    def update_all_items_colors(self):
        """Обновляет цвета всех ячеек в таблице"""
        table = self.ui.tableWidget_sh_web_params
        for row in range(table.rowCount()):
            for col in range(table.columnCount()):
                if item := table.item(row, col):
                    self.update_item_color(item)

    def update_item_color(self, item):
        # Первая строка для выбора скважин
        if item.row() == 0:
            if item.checkState() == QtCore.Qt.Checked:
                item.setBackground(QtGui.QColor(189, 236, 182))  # Зеленый
            else:
                item.setBackground(QtGui.QColor(199, 208, 204))  # Серый
            return

        # Неактивные ячейки
        if not item.flags() & QtCore.Qt.ItemIsUserCheckable:
            item.setBackground(QtGui.QColor(199, 208, 204))
            return

        # Чекбоксы параметров
        if item.checkState() == QtCore.Qt.Checked:
            item.setBackground(QtGui.QColor(189, 236, 182))  # Зеленый
        else:
            item.setBackground(QtGui.QColor(255, 255, 255))  # Белый

    def on_header_clicked(self, index):
        """Обработка клика по заголовку столбца"""
        table = self.ui.tableWidget_sh_web_params
        state = table.horizontalHeaderItem(index).checkState()
        # Меняем состояние всех чекбоксов в столбце
        for row in range(table.rowCount()):
            item = table.item(row, index)
            if item and item.flags() & QtCore.Qt.ItemIsUserCheckable:
                item.setCheckState(state)
        self.update_all_items_colors()
        self.update_selected_wells_lineedit()

    def on_well_checkbox_changed(self, item):
        # ваша логика...
        pass

    def update_selected_wells_lineedit(self):
        # ваша логика...
        pass

class ShWebReader(QtWidgets.QWidget, CheckboxTableMixin):
    signal_sh_web_plot_generated = QtCore.pyqtSignal(list, name='signal_sh_web_plot_generated')
    signal_sh_web_file_generated = QtCore.pyqtSignal(str, dict)

    MIN_SUBPLOT_WIDTH = 300  # Минимальная ширина одного субплота в пикселях

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_ShWebReaderForm()
        self.ui.setupUi(self)

        # Инициализируем поведение чекбоксов
        self.init_checkbox_behavior()

        # Кнопки
        self.ui.pushButton_load_sh_web.clicked.connect(self.load_file)
        self.ui.pushButton_plot_sh_params.clicked.connect(self.on_load_and_plot)
        self.ui.pushButton_save_file.clicked.connect(self.save_file)
        self.ui.checkBox_apply_suffix.stateChanged.connect(self.update_selected_wells_lineedit)

        # Matplotlib Canvas
        self.figure = plt.Figure()
        self.canvas = FigureCanvas(self.figure)
        self.toolbar = NavigationToolbar(self.canvas, self)
        # Добавляем toolbar и canvas в основной layout
        self.ui.verticalLayout_2.addWidget(self.toolbar)
        self.ui.verticalLayout_2.addWidget(self.canvas)

        # Данные
        self.data = {}
        self.reader_counter = 0
        self.params_list = []
        self.file_names = []
        self.num_wells = []

    def compute_cols(self) -> int:
        """Вычисляет количество колонок субплотов по ширине окна"""
        w = self.canvas.width()
        return max(1, w // self.MIN_SUBPLOT_WIDTH)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # При изменении размера окна автоматически перерисовываем графики
        if getattr(self, 'data', None):
            self.plot_data()

    def on_load_and_plot(self):
        # Читаем файл и сразу строим графики
        self.load_file()
        if self.data:
            self.plot_data()

    def plot_data(self, cols: int = None):
        """Строит графики всех скважин в одном окне с адаптивной сеткой и интерактивной легендой"""
        # Очищаем предыдущие графики
        self.figure.clear()

        wells = list(self.data.keys())
        n = len(wells)
        cols = cols or self.compute_cols()
        rows = (n + cols - 1) // cols

        axes = self.figure.subplots(rows, cols, sharex=True)
        # Flatten axes array
        try:
            axes_list = axes.flatten()
        except AttributeError:
            axes_list = [axes]

        all_lines = []
        all_labels = []

        # Рисуем данные
        for ax, well in zip(axes_list, wells):
            df = self.data[well]
            for param in df.columns:
                line, = ax.plot(df.index, df[param], label=param, picker=5)
                all_lines.append(line)
                all_labels.append(param)

            # Форматирование даты на оси X
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            ax.xaxis.set_major_locator(mdates.AutoDateLocator())
            ax.tick_params(axis='x', rotation=30)
            ax.set_title(f"Скважина {well}")

        # Удаляем лишние оси
        for extra_ax in axes_list[n:]:
            self.figure.delaxes(extra_ax)

        # Общая легенда внизу
        legend = self.figure.legend(
            handles=all_lines,
            labels=all_labels,
            loc='lower center',
            ncol=min(4, len(all_lines)),
            frameon=True,
            fontsize='small'
        )
        # Делаем элементы легенды кликабельными
        for text in legend.get_texts():
            text.set_picker(True)

        def on_pick(event):
            artist = event.artist
            label = artist.get_text() if hasattr(artist, 'get_text') else artist.get_label()
            # Переключаем видимость линий
            for line in all_lines:
                if line.get_label() == label:
                    line.set_visible(not line.get_visible())
            self.canvas.draw_idle()

        self.canvas.mpl_connect('pick_event', on_pick)

        self.figure.tight_layout(rect=[0, 0.05, 1, 1])
        self.canvas.draw()

    # Остальные методы (load_file, read_file, update_params_table, save_file и т.д.) остаются без изменений и должны располагаться ниже
