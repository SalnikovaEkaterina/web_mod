from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import QApplication
from colendary_data import DateRangeApp
import datetime
import re

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

import matplotlib.dates as mdates
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import pandas as pd
from pandas import Timestamp

from PyQt5 import QtGui


class NoScrollComboBox(QtWidgets.QComboBox):
    '''
    ComboBox, в котором игнорируется событие прокрутки мыши.
    '''
    def wheelEvent(self, event):
        event.ignore()


class CountHydrostaticPressureWindow(QtWidgets.QDialog):
    ''' Окно, которое появляется при загрузке файла из NGT на вкладке "Инструмент".
        Дает возможность прибавить гидростатическое давление ко всем параметрам, связанным
        с буферным давлением (Рбуф).
    '''

    def __init__(self, wells_params):
        super(CountHydrostaticPressureWindow, self).__init__()
        self.wells_params = wells_params
        self.selected_parameters = {}
        self.sign = None
        self.density = None
        self.depth_tvd = None

        self.init_ui()

        self.params_dict = {
            'Давление': 'P',
            'Дебит нефти': 'Q_oil'
        }

    def init_ui(self):
        self.setWindowTitle("Пересчет давления")
        self.setGeometry(500, 400, 1000, 400)
        layout = QtWidgets.QVBoxLayout(self)

        self.tableWidget = QtWidgets.QTableWidget()

        pressure_params = []

        for params_list in self.wells_params.values():
            for param in params_list:
                if 'буф' in param:
                    pressure_params.append(param)

        self.tableWidget.setRowCount(len(pressure_params))
        self.tableWidget.setColumnCount(4)
        self.tableWidget.setHorizontalHeaderLabels(['Скважина', 'Название параметра', 'Группа', 'Доп. условия'])

        row_idx = 0
        for well, params in self.wells_params.items():
            for param in params:
                if 'буф' in param:
                    self.tableWidget.setItem(row_idx, 0, QtWidgets.QTableWidgetItem(str(well)))
                    self.tableWidget.setItem(row_idx, 1, QtWidgets.QTableWidgetItem(param.replace('\n', ' ').strip()))

                    combo_box = NoScrollComboBox()
                    combo_box.addItems(['Давление'])

                    self.tableWidget.setCellWidget(row_idx, 2, combo_box)

            row_idx += 1

        # Настройка заголовков
        header = self.tableWidget.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.Stretch)  # Растянуть заголовки по ширине

        # Настройка высоты строк
        self.tableWidget.setRowHeight(row_idx, 30)
        self.tableWidget.resizeColumnsToContents()

        # Добавление прокрутки
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.tableWidget)

        layout.addWidget(scroll_area)

        # Добавление кнопок для подтверждения или отмены
        button_layout = QtWidgets.QHBoxLayout()
        confirm_button = QtWidgets.QPushButton("Подтвердить")
        cancel_button = QtWidgets.QPushButton("Отмена")

        confirm_button.clicked.connect(self.save_selection)
        cancel_button.clicked.connect(self.reject)

        button_layout.addWidget(confirm_button)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)

        # Подключение сигналов кнопок
        confirm_button.clicked.connect(self.save_selection)
        cancel_button.clicked.connect(self.reject)

        self.check_comboboxes_for_P()

    def check_comboboxes_for_P(self):

        for row in range(self.tableWidget.rowCount()):

            combo_box_param_groups = self.tableWidget.cellWidget(row, 2)
            curr_condition = combo_box_param_groups.currentText()

            if curr_condition == 'Давление':
                conditions_layout = QtWidgets.QHBoxLayout()

                self.small_combo_box = NoScrollComboBox()
                self.small_combo_box.addItems(['+', '-'])
                self.small_combo_box.setMinimumHeight(30)
                self.small_combo_box.setMinimumWidth(30)
                self.small_combo_box.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
                conditions_layout.addWidget(self.small_combo_box)

                self.density_input = QtWidgets.QSpinBox()
                self.density_input.setMaximum(2000)
                self.density_input.setValue(1000)
                self.density_input.setObjectName("density_input")
                self.density_input.setToolTip("Введите плотность жидкости в кг/м³")
                self.density_input.setMinimumHeight(30)
                self.density_input.setMinimumWidth(50)
                self.density_input.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)
                self.density_input.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
                conditions_layout.addWidget(self.density_input)

                g_label = QtWidgets.QLabel("* g *")
                g_label.setMinimumHeight(30)
                g_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
                conditions_layout.addWidget(g_label)

                self.depth_input = QtWidgets.QSpinBox()
                self.depth_input.setMaximum(10000)
                self.depth_input.setValue(2500)
                self.depth_input.setObjectName("depth_input")
                self.depth_input.setToolTip("Введите глубину (TVD) в метрах")
                self.depth_input.setMinimumHeight(30)
                self.depth_input.setMinimumWidth(50)
                self.depth_input.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)
                self.depth_input.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
                conditions_layout.addWidget(self.depth_input)
                conditions_layout.setAlignment(QtCore.Qt.AlignCenter)

                conditions_layout.setContentsMargins(0, 0, 0, 0)

                conditions_widget = QtWidgets.QWidget()
                conditions_widget.setLayout(conditions_layout)

                self.tableWidget.setCellWidget(row, 3, conditions_widget)
                self.tableWidget.resizeColumnsToContents()

        self.tableWidget.resizeColumnsToContents()

    def save_selection(self):
        for row in range(self.tableWidget.rowCount()):
            well = self.tableWidget.item(row, 0).text()
            param = self.tableWidget.item(row, 1).text()
            combo_box = self.tableWidget.cellWidget(row, 2)
            selection = combo_box.currentText()
            selection = self.params_dict[selection]

            if well not in self.selected_parameters:
                self.selected_parameters[well] = {}

            self.selected_parameters[well][param] = selection

            if param not in self.selected_parameters[well]:
                self.selected_parameters[well][param] = {}  # Создайте новый словарь для параметра

            if selection == 'P':
                # pprint('нашел P')
                item = self.tableWidget.cellWidget(row, 3)
                # Извлекаем конкретные виджеты
                small_combo_box = item.findChild(NoScrollComboBox)  # Предположим, что у вас есть QComboBox
                density_input = item.findChild(QtWidgets.QSpinBox, "density_input")  # QLineEdit для плотности
                depth_input = item.findChild(QtWidgets.QSpinBox, "depth_input")  # QLineEdit для TVD

                # Получаем значения из виджетов
                sign_value = small_combo_box.currentText() if small_combo_box else None
                density_value = density_input.value() if density_input else None
                depth_value = depth_input.value() if depth_input else None

                # print(f"sign_value: {sign_value}, density_value: {density_value}, depth_value: {depth_value}")

                # Сохраняем значения в словаре
                self.selected_parameters[well][param] = {}

                # self.selected_parameters[well][param]['sign']
                self.selected_parameters[well][param]['group'] = selection
                self.selected_parameters[well][param]['sign'] = sign_value
                self.selected_parameters[well][param]['density'] = density_value
                self.selected_parameters[well][param]['tvd'] = depth_value

                # pprint(self.selected_parameters[well][param])

        self.accept()
        return self.selected_parameters
'''
    Окно, которое появляется на вкладке "Выгрузка из Шахматки Desktop" при нажатии
    на кнопку со знаком "+". Предоставляет возможность объединить два или больше параметров
    и положить их на одну ось.
    ВАЖНО: предполагается, что параметры, выбранные для сшивания, не пересекаются по временной
    шкале (т.е. нет значений на одну и ту же дату). Иначе поведение алгоритма непредсказуемо.

    '''

#он извлекает название параметра из первой колонки (param_name) , ищет данные этого параметра в self.param_data
#если данные есть, открывает диалог выбора диапазона дат (DateRangeApp)
#после выбора диапазона:отображает его в виде строки (например: 01.01.2022 — 05.01.2022) сохраняет в item.setData(QtCore.Qt.UserRole + 1, selected_ranges)
class ClickableTableWidget(QtWidgets.QTableWidget):
    def mousePressEvent(self, event):
        item = self.itemAt(event.pos())
        if not item:
            return

        try:
            if item.column() == 1 and item.text() == "+":
                param_item = self.item(item.row(), 0)
                if not param_item:
                    return

                param_name = param_item.text()

                if not hasattr(self, 'param_data'):
                    QtWidgets.QMessageBox.critical(
                        self,
                        "Ошибка данных",
                        "Отсутствует подключение к данным параметров"
                    )
                    return

                param_series = self.param_data.get(param_name)
                if param_series is None:
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Параметр не найден",
                        f"Нет данных для параметра: {param_name}"
                    )
                    return

                if not hasattr(param_series, 'index'):
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Ошибка формата",
                        f"Данные параметра {param_name} имеют неверный формат"
                    )
                    return

                available_dates = sorted(param_series.index.to_list())
                dialog = DateRangeApp(available_dates=available_dates, parent=self)
                if dialog.exec_() == QtWidgets.QDialog.Accepted:
                    selected_ranges = dialog.get_selected_ranges()
                    if selected_ranges:
                        formatted = dialog.get_formatted_ranges()
                        item.setText(formatted)
                        item.setData(QtCore.Qt.UserRole + 1, selected_ranges)



                return

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Неожиданная ошибка",
                f"Произошла ошибка: {str(e)}"
            )

        super().mousePressEvent(event)

class AddParameterWindow(QtWidgets.QDialog):

# выбрать параметры для отображения и сшивания (из списка params);указать временные промежутки для каждого параметра;визуализировать графики для отдельных параметров и для их сшивания;ввести название для нового параметра;и, при необходимости, выполнить сшивание параметров (объединение значений во времени).
    def __init__(self, well, params, param_data=None):
        super(AddParameterWindow, self).__init__()
        self.well = well
        self.params = params
        self.param_data = param_data if param_data is not None else {}
        self.plot_lines = {}
        self.checked_group = None
        self.selected_param_ranges = {}  # Инициализация здесь

        self.param_groups = {
            "pressure": {'AAAРзаб огр инд', 'Рзаб огр инд', 'Pзаб(цднг)', 'Рприем', 'Рст', 'Рзатр',
                         'Pзаб (иссл.)', 'Рбуф', 'Pзаб(Pпр)', 'Pкуст', 'Pзаб(Hд)', 'Рзатр стат'},
            "volume": {'Qн', 'Qж', 'Qж(тн)', 'Qн*'}
        }

        self.tableWidget = ClickableTableWidget()
        self.tableWidget.parent_window = self
        self.tableWidget.param_data = self.param_data

        self.init_ui()
# перебор групп параметров , делится на два типа , обьем , давление и другие
    def get_param_group(self, param):
        for group, members in self.param_groups.items():
            if param in members:
                return group
        return "other"


    def get_param_color(self, param, index=0, plot_type="default"):

        """
            Возвращает цвет для параметра в зависимости от типа графика

            :param param: Название параметра
            :param index: Индекс (для автоматического выбора цвета)
            :param plot_type: Тип графика ("default", "individual", "merged")
            :return: Цвет в формате matplotlib
            """
        # Базовые цвета для разных типов графиков
        color_palettes = {
            "default": ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd'],
            "individual": ['#4e79a7', '#f28e2b', '#e15759', '#76b7b2', '#59a14f'],
            "merged": ['#edc948', '#af7aa1', '#ff9da7', '#9c755f', '#bab0ac']
        }

        param_lower = re.sub(r'[^a-zA-Zа-яА-ЯёЁ0-9]+', '', param.lower())

        # Давление - красные оттенки
        if any(sub in param_lower for sub in ['p', 'р', 'заб', 'прием', 'затр', 'ст', 'куст']):
            if plot_type == "merged":
                return '#ff6b6b'  # светлый красный для сшивки
            return 'r'  # стандартный красный

        # Дебиты нефти - зелёные
        elif 'qн' in param_lower:
            if plot_type == "merged":
                return '#88d8b0'  # пастельный зелёный
            return 'darkseagreen'

        # Дебиты жидкости - синие/фиолетовые
        elif 'qж' in param_lower:
            if plot_type == "merged":
                return '#b5b8ff'  # лавандовый
            return 'purple'

        # Буферное давление - оранжевый
        elif 'буф' in param_lower and '+' not in param_lower:
            return '#FFA500'

        # По умолчанию берём из палитры по индексу
        palette = color_palettes.get(plot_type, color_palettes["default"])
        return palette[index % len(palette)]


    def init_ui(self):
        self.setWindowTitle('Добавление параметров')
        self.resize(1600, 800)

        main_layout = QtWidgets.QHBoxLayout(self)
        left_layout = QtWidgets.QVBoxLayout()

        self.tableWidget = ClickableTableWidget()
        self.tableWidget.setRowCount(len(self.params))
        self.tableWidget.setColumnCount(2)
        self.tableWidget.setHorizontalHeaderLabels([str(self.well), "Дата"])
        self.tableWidget.verticalHeader().setDefaultSectionSize(30)
        self.tableWidget.horizontalHeader().setStretchLastSection(True)
        self.tableWidget.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)

        self.param_name_line_edit = QtWidgets.QLineEdit()

        row = 0
        for param in self.params:
            chkBoxItem = QtWidgets.QTableWidgetItem(param)
            chkBoxItem.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)

            if param in ['Pзаб(Pпр)', 'Рбуф']:
                chkBoxItem.setCheckState(QtCore.Qt.Checked)
                chkBoxItem.setBackground(QtGui.QColor('#90EE90'))
            else:
                chkBoxItem.setCheckState(QtCore.Qt.Unchecked)
                chkBoxItem.setBackground(QtGui.QColor('white'))

            self.tableWidget.setItem(row, 0, chkBoxItem)
            if param in self.param_data:
                series = self.param_data[param]
                dates = sorted(series.index.to_list())  # список доступных дат
                text = f"{len(dates)} дн." if dates else "нет данных"
            else:
                dates = []
                text = "нет данных"

            dateItem = QtWidgets.QTableWidgetItem(text)
            dateItem.setTextAlignment(QtCore.Qt.AlignCenter)
            dateItem.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
            dateItem.setData(QtCore.Qt.UserRole, dates)  # Сохраняем список доступных дат
            self.tableWidget.setItem(row, 1, dateItem)

            row += 1

        self.tableWidget.itemChanged.connect(self.on_checkbox_changed)
        self.tableWidget.cellClicked.connect(self.on_table_cell_clicked)

        param_name_label = QtWidgets.QLabel("Название параметра:")
        param_name_label.setStyleSheet("font-weight: bold;")

        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.tableWidget)
        scroll_area.setMinimumWidth(400)

        left_layout.addWidget(scroll_area)
        left_layout.addWidget(param_name_label)
        left_layout.addWidget(self.param_name_line_edit)

        # КНОПКИ
        button_layout = QtWidgets.QHBoxLayout()
        confirm_button = QtWidgets.QPushButton("Добавить")
        merge_button = QtWidgets.QPushButton("Сшивание")
        cancel_button = QtWidgets.QPushButton("Отмена")

        confirm_button.clicked.connect(self.save_selection)
        merge_button.clicked.connect(self.on_merge_clicked)
        cancel_button.clicked.connect(self.reject)

        button_layout.addWidget(confirm_button)
        button_layout.addWidget(merge_button)
        button_layout.addWidget(cancel_button)

        # ОБЯЗАТЕЛЬНО добавляем layout с кнопками в левую часть
        left_layout.addLayout(button_layout)

        # === ПРАВАЯ ЧАСТЬ (графики) ===
        right_layout = QtWidgets.QVBoxLayout()
        right_layout.setSpacing(2)
        right_layout.setContentsMargins(5, 2, 5, 2)

        from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar

        # --- Первый график (параметры) ---
        self.plot1 = FigureCanvas(Figure(figsize=(10, 5)))
        self.ax1 = self.plot1.figure.add_subplot(111)
        self.ax1.grid(True, linestyle=':', alpha=0.7)
        self.ax1.set_title("Зависимости параметров", pad=20, fontsize=12, fontweight='bold')
        self.ax1.set_ylabel("Значение", fontsize=10)
        self.ax1.set_xlabel("Дата", fontsize=10)
        self.ax1.xaxis.set_major_locator(mdates.AutoDateLocator(maxticks=12))
        self.ax1.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m.%Y'))
        self.plot1.figure.autofmt_xdate(rotation=45, ha='right')

        toolbar1 = NavigationToolbar(self.plot1, self)
        toolbar1.setIconSize(QtCore.QSize(16, 16))
        toolbar1.setStyleSheet("QToolBar { spacing: 2px; margin: 0px; padding: 0px; }")
        right_layout.addWidget(toolbar1)
        right_layout.addWidget(self.plot1, stretch=1)

        # --- Второй график (сшивание) ---
        self.plot2 = FigureCanvas(Figure(figsize=(10, 5)))
        self.ax2 = self.plot2.figure.add_subplot(111)
        self.ax2.set_title("Сшивание", pad=15, fontsize=11)
        self.ax2.grid(True, linestyle=':', alpha=0.5)

        toolbar2 = NavigationToolbar(self.plot2, self)
        toolbar2.setIconSize(QtCore.QSize(16, 16))
        toolbar2.setStyleSheet("QToolBar { spacing: 2px; margin: 0px; padding: 0px; }")
        right_layout.addWidget(toolbar2)
        right_layout.addWidget(self.plot2, stretch=1)

        # Основной макет
        main_layout.addLayout(left_layout, stretch=1)
        main_layout.addLayout(right_layout, stretch=3)
        self.setLayout(main_layout)

        self.fitToTable(self.tableWidget)
# отвечает за столбец с датой
    def on_table_cell_clicked(self, row, col):
        if col != 1:
            return

        param_item = self.tableWidget.item(row, 0)
        date_item = self.tableWidget.item(row, 1)

        if not param_item or not date_item:
            return

        param_name = param_item.text()
        available_dates = date_item.data(QtCore.Qt.UserRole)  # Список всех возможных дат

        if not available_dates:
            QtWidgets.QMessageBox.information(self, "Нет данных", "Нет доступных дат для параметра.")
            return

#Сохраняем диапазоны:
        dialog = DateRangeApp(available_dates=available_dates, parent=self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            selected_ranges = dialog.get_selected_ranges()
            formatted = dialog.get_formatted_ranges()


            date_item.setText(formatted)
            date_item.setData(QtCore.Qt.UserRole + 1, selected_ranges)

            def format_date(d):
                if isinstance(d, QtCore.QDate):
                    return d.toString("dd.MM.yyyy")
                elif isinstance(d, (datetime.date, datetime.datetime)):
                    return d.strftime("%d.%m.%Y")
                elif isinstance(d, pd.Timestamp):
                    return d.strftime("%d.%m.%Y")
                return str(d)

            tooltip_text = "\n".join(f"{format_date(start)} — {format_date(end)}" for start, end in selected_ranges)
            date_item.setToolTip(tooltip_text)

            if param_item.checkState() == QtCore.Qt.Checked:
                if param_name in self.param_data:
                    full_series = self.param_data[param_name]
                    filtered_series = self.get_filtered_series(param_name, full_series)
                    self.plot_parameter(param_name, filtered_series)

#делает всё, чтобы после щелчка по чекбоксу: изменить визуал в таблице,показать или убрать график,не дать выбрать параметры из разных групп,
#и обновить название нового объединённого параметра.


    def on_checkbox_changed(self, item):
        if item.column() != 0:
            return

        param = item.text()
        is_checked = item.checkState() == QtCore.Qt.Checked


        item.setBackground(QtGui.QColor('#90EE90') if is_checked else QtGui.QColor('white'))
        font = item.font()
        font.setBold(is_checked)
        item.setFont(font)


        if is_checked:
            if param in self.param_data:
                full_series = self.param_data[param]
                # Применяем фильтрацию по выбранным диапазонам
                filtered_series = self.get_filtered_series(param, full_series)
                if not filtered_series.empty:
                    self.plot_parameter(param, filtered_series)
        else:
            self.remove_plot(param)

        self.update_table_state()
        self.set_line_edit()

    def plot_parameter(self, param, series):
        print(f"\n--- Начало отрисовки параметра {param} ---")
        print(f"Размер series: {len(series)}")
        if not series.empty:
            print(f"Первые 5 значений:\n{series.head()}")
            print(f"Тип индекса: {type(series.index[0])}")
        # Удаляем старый график параметра
        if param in self.plot_lines:
            for line in self.plot_lines[param]['lines']:
                try:
                    line.remove()
                except:
                    pass
            del self.plot_lines[param]

        if series.empty or series.index.empty:
            print(f"[{param}] Пустая серия, не строим.")
            return

        all_lines = []
        all_segments = []
        patch_color = None  # сюда сохраним нужный цвет для патча

        for row in range(self.tableWidget.rowCount()):
            item = self.tableWidget.item(row, 0)
            if item and item.text() == param:
                date_item = self.tableWidget.item(row, 1)
                ranges = date_item.data(QtCore.Qt.UserRole + 1)

                if not ranges:
                    full_series = self.param_data.get(param)
                    if full_series is not None and not full_series.empty:
                        color = self.get_param_color(param, 0, plot_type="individual")
                        patch_color = color
                        line, = self.ax1.plot(
                            full_series.index,
                            full_series.values,
                            '.',
                            color=color,
                            label=f"{param}: весь диапазон"
                        )
                        all_lines.append(line)
                        all_segments.append(full_series)
                    continue

                for i, (start_raw, end_raw) in enumerate(ranges):
                    try:
                        def to_timestamp(d):
                            if isinstance(d, QtCore.QDate):
                                return pd.Timestamp(d.toPyDate())
                            elif isinstance(d, (pd.Timestamp, pd.DatetimeIndex)):
                                return pd.Timestamp(d)
                            elif isinstance(d, (datetime.date, datetime.datetime)):
                                return pd.Timestamp(d)
                            else:
                                raise ValueError(f"Неизвестный тип даты: {type(d)}")

                        start = to_timestamp(start_raw)
                        end = to_timestamp(end_raw)

                        if start > end:
                            start, end = end, start

                        part = series.loc[(series.index >= start) & (series.index <= end)]

                        if not part.empty:
                            color = self.get_param_color(param, i, plot_type="individual")
                            patch_color = color if patch_color is None else patch_color
                            line, = self.ax1.plot(
                                part.index,
                                part.values,
                                '.',
                                color=color,
                                label=f"{param}: {start.strftime('%d.%m')} — {end.strftime('%d.%m')}"
                            )
                            all_lines.append(line)
                            all_segments.append(part)

                    except Exception as e:
                        print(f"[{param}] Ошибка при отрисовке диапазона: {e}")

        if all_lines:
            all_data = pd.concat(all_segments)
            patch = mpatches.Patch(
                color=patch_color or 'gray',
                label=f"{param} (max: {all_data.max():.2f}, min: {all_data.min():.2f})"
            )
            self.plot_lines[param] = {'lines': all_lines, 'patch': patch}

        self.ax1.relim()
        self.ax1.autoscale_view()
        self.plot1.draw()
        self.update_legend()
#Удаление графика параметра
    def remove_plot(self, param):

        if param in self.plot_lines:
            for line in self.plot_lines[param]['lines']:
                try:
                    line.remove()
                except:
                    pass
            del self.plot_lines[param]
            self.update_legend()

#Обновление легенды графика
    def update_legend(self):

        patches = [data['patch'] for data in self.plot_lines.values()]
        if patches:
            self.ax1.legend(handles=patches, bbox_to_anchor=(1.05, 1), loc='upper left')
        elif hasattr(self.ax1, 'legend_'):
            self.ax1.legend_.remove()
        self.ax1.relim()
        self.ax1.autoscale_view()
        self.plot1.draw()
#Если что-то нашли — объединяем куски, сортируем по времени и возвращаем.Иначе — возвращается пустой Series.
    def get_filtered_series(self, param, series):
        """Фильтрует временной ряд по выбранным диапазонам с проверками"""
        for row in range(self.tableWidget.rowCount()):
            item = self.tableWidget.item(row, 0)
            if item and item.text() == param:
                date_item = self.tableWidget.item(row, 1)
                ranges = date_item.data(QtCore.Qt.UserRole + 1)

                if not ranges:
                    print(f"[{param}] Нет выбранных диапазонов.")
                    continue

                parts = []

                for start_raw, end_raw in ranges:
                    try:
                        # === Преобразуем в pandas.Timestamp, если это QDate или datetime.date ===
                        def to_timestamp(d):
                            if isinstance(d, QtCore.QDate):
                                return pd.Timestamp(d.toPyDate())
                            elif isinstance(d, (pd.Timestamp, pd.DatetimeIndex)):
                                return pd.Timestamp(d)
                            elif isinstance(d, (datetime.date, datetime.datetime)):
                                return pd.Timestamp(d)
                            else:
                                raise ValueError(f"Неизвестный тип даты: {type(d)}")

                        start = to_timestamp(start_raw)
                        end = to_timestamp(end_raw)

                        if start > end:
                            start, end = end, start

                        print(f"[{param}] Проверка диапазона: {start} — {end}")
                        print(f"[{param}] Индекс временного ряда от {series.index.min()} до {series.index.max()}")

                        # === Безопасная фильтрация по маске ===
                        mask = (series.index >= start) & (series.index <= end)
                        part = series.loc[mask]

                        print(f"[{param}] Найдено точек в диапазоне: {len(part)}")
                        if not part.empty:
                            parts.append(part)

                    except Exception as e:
                        print(f"[{param}] Ошибка при обработке диапазона: {e}")

                if parts:
                    filtered = pd.concat(parts).sort_index()
                    print(f"[{param}] Отфильтровано всего {len(filtered)} точек")
                    return filtered
                else:
                    print(f"[{param}] Все диапазоны пустые или неверные")
                    return pd.Series(dtype=float)

        print(f"[{param}] Не найден параметр в таблице.")
        return series

    def save_selection(self):
        self.new_param_name = self.param_name_line_edit.text().strip()
        self.selected_param_ranges = {}  # ключ: имя параметра → список диапазонов QDate

        for row in range(self.tableWidget.rowCount()):
            param_item = self.tableWidget.item(row, 0)
            date_item = self.tableWidget.item(row, 1)

            if not param_item or not date_item:
                continue

            param_name = param_item.text()
            ranges = date_item.data(QtCore.Qt.UserRole + 1)  # Список (start_qdate, end_qdate)

            if ranges:
                self.selected_param_ranges[param_name] = ranges

        # Проверка: есть ли вообще выбранные интервалы?
        if not self.selected_param_ranges:
            QtWidgets.QMessageBox.warning(self, "Нет выбранных интервалов", "Вы не выбрали ни одного диапазона.")
            return

        self.accept()
        return self.new_param_name
#построения графика при выборе параметра; удаления графика при снятии галочки; обработки ошибок (например, пустые данные);
#обновления интерфейса (цвет, название, блокировка других групп параметров).
    def on_checkbox_changed(self, item):
        if item.column() != 0:
            return

        param = item.text()
        is_checked = item.checkState() == QtCore.Qt.Checked

        # Обновляем стиль ячейки
        item.setBackground(QtGui.QColor('#90EE90') if is_checked else QtGui.QColor('white'))
        font = item.font()
        font.setBold(is_checked)
        item.setFont(font)

        # Построение графика
        if is_checked:
            if param in self.param_data:
                full_series = self.param_data[param]
                filtered_series = self.get_filtered_series(param, full_series)
                if not filtered_series.empty:
                    self.plot_parameter(param, filtered_series)
                else:
                    QtWidgets.QMessageBox.information(self, "Нет данных",
                                                      f"У параметра '{param}' нет точек в выбранных диапазонах.")
                    item.setCheckState(QtCore.Qt.Unchecked)
                    self.remove_plot(param)
        else:
            self.remove_plot(param)

        self.update_table_state()
        self.set_line_edit()
#собирает и проверяет выбранные пользователем параметры; фильтрует данные по выбранным диапазонам;
#объединяет ряды;рисует объединённый график;НО не сохраняет его в основной набор данных, и не возвращает его наружу.
    def on_merge_clicked(self):
        selected_params = []
        for row in range(self.tableWidget.rowCount()):
            item = self.tableWidget.item(row, 0)
            if item and item.checkState() == QtCore.Qt.Checked:
                selected_params.append(item.text())

        if not selected_params:
            QtWidgets.QMessageBox.warning(self, "Нет параметров", "Выберите параметры для сшивания.")
            return

        series_list = []
        for p in selected_params:
            if p not in self.param_data:
                QtWidgets.QMessageBox.warning(self, "Нет данных", f"Нет данных по параметру: {p}")
                return
            full_series = self.param_data[p]
            filtered_series = self.get_filtered_series(p, full_series)
            if filtered_series.empty:
                QtWidgets.QMessageBox.information(self, "Нет данных", f"У параметра '{p}' нет данных.")
                return
            series_list.append(filtered_series)

        # Проверка на пересекающиеся даты
        all_indexes = pd.Index([])
        for s in series_list:
            all_indexes = all_indexes.append(s.index)

        duplicated = all_indexes[all_indexes.duplicated()]
        if not duplicated.empty:
            reply = QtWidgets.QMessageBox.question(
                self,
                "Совпадение дат!",
                "Обнаружены совпадающие даты!\nПродолжить сшивание?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            if reply == QtWidgets.QMessageBox.No:
                return

        try:
            merged_series = pd.concat(series_list).sort_index()
            merged_series.index = pd.to_datetime(merged_series.index)
            merged_series = merged_series[~merged_series.index.duplicated(keep='first')]
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Ошибка сшивания", str(e))
            return

        new_param_name = self.param_name_line_edit.text().strip() or "+".join(selected_params)

        # ⬇ Сохраняем, чтобы потом использовать в основном окне
        self.new_param_name = new_param_name
        self.new_param_series = merged_series

        self.ax2.clear()
        self.ax2.set_title("Сшитый параметр", fontsize=11)
        self.ax2.grid(True, linestyle=':', alpha=0.7)

        color = self.get_param_color(selected_params[0], plot_type="merged")
        self.ax2.scatter(
            merged_series.index,
            merged_series.values,
            color=color,
            s=25,
            label=new_param_name,
            alpha=0.8,
            edgecolors='w',
            linewidths=0.5
        )
        self.ax2.set_ylabel("Значение")
        self.ax2.set_xlabel("Дата")
        self.ax2.legend(loc='upper left', fontsize=9)
        self.plot2.draw()

        QtWidgets.QMessageBox.information(self, "Успех", f"Параметр '{new_param_name}' успешно сшит.")
#Ограничить одновременный выбор параметров только одной группы (например, давления или объема), чтобы предотвратить сшивание несовместимых величин.
    def update_table_state(self):
        self.tableWidget.blockSignals(True)

        active_group = None
        for row in range(self.tableWidget.rowCount()):
            item = self.tableWidget.item(row, 0)
            if item is not None and item.checkState() == QtCore.Qt.Checked:
                param = item.text()
                active_group = self.get_param_group(param)
                break

        for row in range(self.tableWidget.rowCount()):
            item = self.tableWidget.item(row, 0)
            if item is None:
                continue

            param = item.text()
            group = self.get_param_group(param)
            is_checked = item.checkState() == QtCore.Qt.Checked

            # Разрешаем или запрещаем редактирование
            if active_group and group != active_group and not is_checked:
                item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEnabled)
                item.setBackground(QtGui.QColor('#E0E0E0'))  # серый фон
            else:
                item.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
                if not is_checked:
                    item.setBackground(QtGui.QColor('white'))

        self.tableWidget.blockSignals(False)

    def set_line_edit(self, item=None):
        self.params_to_merge = []
        for row in range(self.tableWidget.rowCount()):
            item = self.tableWidget.item(row, 0)
            if item is not None and item.checkState() == QtCore.Qt.Checked:
                self.params_to_merge.append(item.text())
        self.param_name_line_edit.setText(' + '.join(self.params_to_merge))

    def save_selection(self):
        self.new_param_name = self.param_name_line_edit.text().strip()

        if not self.new_param_name or self.new_param_series is None:
            QtWidgets.QMessageBox.warning(self, "Нет сшивания", "Вы не выполнили сшивание параметров.")
            return

        self.selected_param_ranges = {}

        for row in range(self.tableWidget.rowCount()):
            param_item = self.tableWidget.item(row, 0)
            date_item = self.tableWidget.item(row, 1)

            if not param_item or not date_item:
                continue

            param_name = param_item.text()
            ranges = date_item.data(QtCore.Qt.UserRole + 1)
            if ranges:
                self.selected_param_ranges[param_name] = ranges

        self.accept()
        return self.new_param_name



    def fitToTable(self, table):
        table.resizeColumnsToContents()
        table.resizeRowsToContents()
        width = table.verticalHeader().size().width()
        width += sum(table.columnWidth(i) for i in range(table.columnCount()))
        height = table.horizontalHeader().size().height()
        height += sum(table.rowHeight(i) for i in range(table.rowCount()))
        self.resize(max(width + 50, 1400), max(height + 200, 800))

    def show_dates_popup(self, row):
        item = self.tableWidget.item(row, 1)
        if not item:
            return
        dates = item.data(QtCore.Qt.UserRole)
        if not dates:
            QtWidgets.QMessageBox.information(self, "Даты", "Нет доступных дат.")
            return

        formatted = '\n'.join(d.strftime('%d.%m.%Y') for d in dates)
        QtWidgets.QMessageBox.information(self, "Даты параметра", formatted)


class ParameterSelectionWindow(QtWidgets.QDialog):
    '''
    Окно, которое появляется при сохранении предобработанных данных на вкладках
    "Шахматка Web" и "Шахматка Desktop".

    Дает возможность проконтролировать определение групп параметров (необходимо
    для работы на вкладке "Инструмент"), а также пересчет буферного давления на гидростатическое
    давление и пересчет Qн из т/сут в м3/сут.

    ФИЧА: если сохраняем сшитый параметр (см. описание AddParameterWindow), в котором есть
    буферное давление, то пересчитается только эта часть.

    '''

    def __init__(self, wells_params):
        super(ParameterSelectionWindow, self).__init__()
        self.wells_params = wells_params
        self.selected_parameters = {}
        self.sign = None  # Знак ('+' или '-')
        self.density = None  # Плотность
        self.depth_tvd = None  # Глубина

        self.init_ui()

        self.params_dict = {
            'Давление': 'P',
            'Приемистость': 'Q_inj',
            'Дебит жидкости': 'Q_total',
            'Дебит нефти': 'Q_oil',
            'Обводненность': 'WC',
            'Не выгружать': 'None'
        }

    def init_ui(self):
        self.setWindowTitle("Выбор параметров")
        self.setGeometry(500, 400, 1000, 400)  # Установка размера окна
        layout = QtWidgets.QVBoxLayout(self)

        self.tableWidget = QtWidgets.QTableWidget()
        total_rows = sum(len(params) for params in self.wells_params.values())
        self.tableWidget.setRowCount(total_rows)
        self.tableWidget.setColumnCount(4)
        self.tableWidget.setHorizontalHeaderLabels(['Скважина', 'Название параметра', 'Группа', 'Доп. условия'])

        row_idx = 0
        for well, params in self.wells_params.items():
            for param in params:
                self.tableWidget.setItem(row_idx, 0, QtWidgets.QTableWidgetItem(well))
                self.tableWidget.setItem(row_idx, 1, QtWidgets.QTableWidgetItem(param))

                combo_box = NoScrollComboBox()
                combo_box.addItems(
                    ['Давление', 'Приемистость', 'Дебит жидкости', 'Дебит нефти', 'Обводненность', 'Не выгружать'])

                if 'буф' in param:
                    combo_box.setCurrentIndex(0)
                elif 'P' in param or 'Р' in param:
                    combo_box.setCurrentIndex(0)
                elif 'бв' in param:
                    combo_box.setCurrentIndex(4)
                elif 'Qн' in param:
                    combo_box.setCurrentIndex(3)
                elif 'Qж' in param:
                    combo_box.setCurrentIndex(2)
                elif 'Qпр' in param:
                    combo_box.setCurrentIndex(1)
                else:
                    combo_box.setCurrentIndex(5)

                combo_box.currentIndexChanged.connect(lambda index, r=row_idx: self.on_combobox_changed(index, r))
                self.tableWidget.setCellWidget(row_idx, 2, combo_box)
                row_idx += 1

        # Настройка заголовков
        header = self.tableWidget.horizontalHeader()
        # header.setSectionResizeMode(QtWidgets.QHeaderView.Stretch)  # Растянуть заголовки по ширине
        header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)

        # Настройка высоты строк
        self.tableWidget.setRowHeight(row_idx, 30)
        self.tableWidget.resizeColumnsToContents()

        # Добавление прокрутки
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.tableWidget)

        layout.addWidget(scroll_area)

        # Добавление кнопок для подтверждения или отмены
        button_layout = QtWidgets.QHBoxLayout()
        confirm_button = QtWidgets.QPushButton("Подтвердить")
        cancel_button = QtWidgets.QPushButton("Отмена")

        button_layout.addWidget(confirm_button)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)

        # Подключение сигналов кнопок
        confirm_button.clicked.connect(self.save_selection)
        cancel_button.clicked.connect(self.reject)

        # self.fitToTable(self.tableWidget)

        self.check_comboboxes_for_P_and_Q()

    def check_comboboxes_for_P_and_Q(self):

        for row in range(self.tableWidget.rowCount()):

            combo_box_param_groups = self.tableWidget.cellWidget(row, 2)
            curr_condition = combo_box_param_groups.currentText()

            if curr_condition == 'Давление':
                conditions_layout = QtWidgets.QHBoxLayout()

                self.small_combo_box = NoScrollComboBox()
                self.small_combo_box.addItems(['+', '-'])
                self.small_combo_box.setMinimumHeight(30)
                self.small_combo_box.setMinimumWidth(30)
                self.small_combo_box.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
                conditions_layout.addWidget(self.small_combo_box)

                self.density_input = QtWidgets.QSpinBox()
                self.density_input.setMaximum(2000)
                self.density_input.setValue(1000)
                self.density_input.setObjectName("density_input")
                self.density_input.setToolTip("Введите плотность жидкости в кг/м³")
                self.density_input.setMinimumHeight(30)
                self.density_input.setMinimumWidth(50)
                self.density_input.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)
                self.density_input.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
                conditions_layout.addWidget(self.density_input)

                g_label = QtWidgets.QLabel(" * g *")
                g_label.setMinimumHeight(30)
                g_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
                conditions_layout.addWidget(g_label)

                self.depth_input = QtWidgets.QSpinBox()
                self.depth_input.setMaximum(10000)
                self.depth_input.setValue(2500)
                self.depth_input.setObjectName("depth_input")
                self.depth_input.setToolTip("Введите глубину (TVD) в метрах")
                self.depth_input.setMinimumHeight(30)
                self.depth_input.setMinimumWidth(50)
                self.depth_input.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)
                self.depth_input.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
                conditions_layout.addWidget(self.depth_input)
                conditions_layout.setAlignment(QtCore.Qt.AlignCenter)

                conditions_layout.setContentsMargins(0, 0, 0, 0)

                conditions_widget = QtWidgets.QWidget()
                conditions_widget.setLayout(conditions_layout)

                self.tableWidget.setCellWidget(row, 3, conditions_widget)
                self.tableWidget.resizeColumnsToContents()

            if curr_condition == 'Дебит нефти':
                conditions_layout = QtWidgets.QHBoxLayout()

                rho_label = QtWidgets.QLabel('Уд. плотность: ')
                rho_label.setMinimumHeight(30)
                conditions_layout.addWidget(rho_label)

                self.rho_input = QtWidgets.QSpinBox()
                self.rho_input.setMaximum(2000)
                self.rho_input.setValue(860)
                self.rho_input.setObjectName("rho_input")
                self.rho_input.setToolTip("Введите удельную плотность нефти")
                self.rho_input.setMinimumHeight(30)
                self.rho_input.setMinimumWidth(75)
                self.rho_input.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)
                self.rho_input.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
                conditions_layout.addWidget(self.rho_input)

                rho_unit_cbox = NoScrollComboBox()
                rho_unit_cbox.addItems(['кг/м³', 'г/см³'])
                rho_unit_cbox.setMinimumHeight(30)
                rho_unit_cbox.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
                conditions_layout.addWidget(rho_unit_cbox)

                b_label = QtWidgets.QLabel('B: ')
                b_label.setMinimumHeight(40)
                b_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
                conditions_layout.addWidget(b_label)

                self.b_input = QtWidgets.QDoubleSpinBox()
                self.b_input.setMaximum(100)
                self.b_input.setValue(1.00)
                self.b_input.setObjectName("b_input")
                self.b_input.setToolTip("Введите значение объемного коэффициента")
                self.b_input.setMinimumHeight(30)
                self.b_input.setMinimumWidth(75)
                self.b_input.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)
                self.b_input.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
                conditions_layout.addWidget(self.b_input)

                conditions_layout.setContentsMargins(0, 0, 0, 0)

                conditions_layout.setAlignment(QtCore.Qt.AlignCenter)

                conditions_widget = QtWidgets.QWidget()
                conditions_widget.setLayout(conditions_layout)

                self.tableWidget.setCellWidget(row, 3, conditions_widget)
                self.tableWidget.resizeColumnsToContents()
        self.tableWidget.resizeColumnsToContents()
        self.fitToTable(self.tableWidget)

    def on_combobox_changed(self, index, row):

        combo_box_param_groups = self.tableWidget.cellWidget(row, 2)
        selected_item = combo_box_param_groups.currentText()

        self.clear_row_widgets(row)

        if selected_item == 'Давление':
            conditions_layout = QtWidgets.QHBoxLayout()

            self.small_combo_box = NoScrollComboBox()
            self.small_combo_box.addItems(['+', '-'])
            self.small_combo_box.setMinimumHeight(30)
            self.small_combo_box.setMinimumWidth(30)
            self.small_combo_box.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
            self.small_combo_box.view().setAutoScroll(False)
            conditions_layout.addWidget(self.small_combo_box)

            self.density_input = QtWidgets.QSpinBox()
            self.density_input.setMaximum(2000)
            self.density_input.setValue(1000)
            self.density_input.setObjectName("density_input")
            self.density_input.setToolTip("Введите плотность жидкости в кг/м³")
            self.density_input.setMinimumHeight(30)
            self.density_input.setMinimumWidth(50)
            self.density_input.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)
            self.density_input.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
            conditions_layout.addWidget(self.density_input)

            g_label = QtWidgets.QLabel(" * g *")
            g_label.setMinimumHeight(30)
            g_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
            conditions_layout.addWidget(g_label)

            self.depth_input = QtWidgets.QSpinBox()
            self.depth_input.setMaximum(10000)
            self.depth_input.setValue(2500)
            self.depth_input.setObjectName("depth_input")
            self.depth_input.setToolTip("Введите глубину (TVD) в метрах")
            self.depth_input.setMinimumHeight(30)
            self.depth_input.setMinimumWidth(50)
            self.depth_input.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)
            self.depth_input.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
            conditions_layout.addWidget(self.depth_input)
            conditions_layout.setAlignment(QtCore.Qt.AlignCenter)

            conditions_layout.setContentsMargins(0, 0, 0, 0)

            conditions_widget = QtWidgets.QWidget()
            conditions_widget.setLayout(conditions_layout)

            self.tableWidget.setCellWidget(row, 3, conditions_widget)
            self.tableWidget.resizeColumnsToContents()

        if selected_item == 'Дебит нефти':
            conditions_layout = QtWidgets.QHBoxLayout()

            rho_label = QtWidgets.QLabel('Уд. плотность: ')
            rho_label.setMinimumHeight(30)
            conditions_layout.addWidget(rho_label)

            self.rho_input = QtWidgets.QSpinBox()
            self.rho_input.setMaximum(2000)
            self.rho_input.setValue(860)
            self.rho_input.setObjectName("rho_input")
            self.rho_input.setToolTip("Введите удельную плотность нефти")
            self.rho_input.setMinimumHeight(30)
            self.rho_input.setMinimumWidth(75)
            self.rho_input.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)
            self.rho_input.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
            conditions_layout.addWidget(self.rho_input)

            rho_unit_cbox = NoScrollComboBox()
            rho_unit_cbox.addItems(['кг/м³', 'г/см³'])
            rho_unit_cbox.setMinimumHeight(30)
            rho_unit_cbox.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
            conditions_layout.addWidget(rho_unit_cbox)

            b_label = QtWidgets.QLabel('B: ')
            b_label.setMinimumHeight(40)
            b_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
            conditions_layout.addWidget(b_label)

            self.b_input = QtWidgets.QDoubleSpinBox()
            self.b_input.setMaximum(100)
            self.b_input.setValue(1.00)
            self.b_input.setObjectName("b_input")
            self.b_input.setToolTip("Введите значение объемного коэффициента")
            self.b_input.setMinimumHeight(30)
            self.b_input.setMinimumWidth(75)
            self.b_input.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)
            self.b_input.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
            conditions_layout.addWidget(self.b_input)

            conditions_layout.setContentsMargins(0, 0, 0, 0)

            conditions_layout.setAlignment(QtCore.Qt.AlignCenter)

            conditions_widget = QtWidgets.QWidget()
            conditions_widget.setLayout(conditions_layout)

            self.tableWidget.setCellWidget(row, 3, conditions_widget)
            self.tableWidget.resizeColumnsToContents()

        self.tableWidget.resizeColumnsToContents()

    def clear_row_widgets(self, row):
        self.tableWidget.removeCellWidget(row, 3)

    def save_selection(self):
        for row in range(self.tableWidget.rowCount()):
            well = self.tableWidget.item(row, 0).text()
            param = self.tableWidget.item(row, 1).text()
            combo_box = self.tableWidget.cellWidget(row, 2)
            selection = combo_box.currentText()
            selection = self.params_dict[selection]

            if well not in self.selected_parameters:
                self.selected_parameters[well] = {}

            self.selected_parameters[well][param] = selection

            if param not in self.selected_parameters[well]:
                self.selected_parameters[well][param] = {}  # Создайте новый словарь для параметра

            if selection == 'P':
                # pprint('нашел P')
                item = self.tableWidget.cellWidget(row, 3)
                # Извлекаем конкретные виджеты
                small_combo_box = item.findChild(NoScrollComboBox)  # Предположим, что у вас есть QComboBox
                density_input = item.findChild(QtWidgets.QSpinBox, "density_input")  # QLineEdit для плотности
                depth_input = item.findChild(QtWidgets.QSpinBox, "depth_input")  # QLineEdit для TVD

                # Получаем значения из виджетов
                sign_value = small_combo_box.currentText() if small_combo_box else None
                density_value = density_input.value() if density_input else None
                depth_value = depth_input.value() if depth_input else None

                # print(f"sign_value: {sign_value}, density_value: {density_value}, depth_value: {depth_value}")

                # Сохраняем значения в словаре
                self.selected_parameters[well][param] = {}

                # self.selected_parameters[well][param]['sign']
                self.selected_parameters[well][param]['group'] = selection
                self.selected_parameters[well][param]['sign'] = sign_value
                self.selected_parameters[well][param]['density'] = density_value
                self.selected_parameters[well][param]['tvd'] = depth_value

                # pprint(self.selected_parameters[well][param])

            elif selection == 'Q_oil':
                item = self.tableWidget.cellWidget(row, 3)

                rho_input = item.findChild(QtWidgets.QSpinBox, "rho_input")  # QLineEdit для плотности
                rho_unit_cbox = item.findChild(QtWidgets.QComboBox)
                b_input = item.findChild(QtWidgets.QDoubleSpinBox, "b_input")
                rho_value = rho_input.text() if rho_input else None
                rho_unit_value = rho_unit_cbox.currentText() if rho_unit_cbox else None
                b_value = b_input.text().replace(',', '.') if b_input else None

                # Сохраняем значения в словаре
                self.selected_parameters[well][param] = {}
                # self.selected_parameters[well][param]['sign']
                self.selected_parameters[well][param]['group'] = selection
                self.selected_parameters[well][param]['rho'] = rho_value
                self.selected_parameters[well][param]['rho_unit'] = rho_unit_value
                self.selected_parameters[well][param]['B'] = b_value

            elif selection == 'None':
                pass


            else:
                self.selected_parameters[well][param] = selection

        # print("Выбранные параметры:", self.selected_parameters)
        self.accept()
        return self.selected_parameters

    def fitToTable(self, table):

        x = table.verticalHeader().size().width()
        for i in range(table.columnCount()):
            x += table.columnWidth(i)
        y = table.horizontalHeader().size().height()
        for i in range(table.rowCount()):
            y += table.rowHeight(i)
        self.resize(x + 50, y + 100)