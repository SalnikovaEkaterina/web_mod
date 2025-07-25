import os.path
import sys
from calendar import monthrange
from datetime import datetime
from datetime import timedelta
from colendary_data import DateRangeApp


import openpyxl
import pandas as pd
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import QApplication
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

from ui_form_sh_web_reader import Ui_ShWebReaderForm

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from probuyu.read_sh_desktop_module.mini_windows import ParameterSelectionWindow


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
        table.cellClicked.connect(self.toggle_checkbox_on_click)  # <- добавлено

        self.update_all_items_colors()

    def update_all_items_colors(self):
        """Обновляет цвета всех ячеек в таблице"""
        table = self.ui.tableWidget_sh_web_params
        for row in range(table.rowCount()):
            for col in range(table.columnCount()):
                if item := table.item(row, col):
                    self.update_item_color(item)

    def update_item_color(self, item):
        """Обновление цвета ячеек в зависимости от состояния чекбокса"""
        table = self.ui.tableWidget_sh_web_params
        if item.row() == 0:
            if item.checkState() == QtCore.Qt.Checked:
                item.setBackground(QtGui.QColor(189, 236, 182))  # Зеленый
            else:
                item.setBackground(QtGui.QColor(199, 208, 204))  # Серый
            return
        if item.text().strip().lower() == "примечание":
            item.setBackground(QtGui.QColor(199, 208, 204))  # Серый
            return

        if not item.flags() & QtCore.Qt.ItemIsUserCheckable:
            item.setBackground(QtGui.QColor(199, 208, 204))  # Серый
            return

        item.setBackground(QtGui.QColor(255, 255, 255))  # Всегда белый

    def on_header_clicked(self, index):
        """Обработка клика по заголовку столбца"""
        table = self.ui.tableWidget_sh_web_params
        current_state = self.checkbox_states.get(index, False)
        new_state = not current_state
        self.checkbox_states[index] = new_state

        for row in range(table.rowCount()):
            item = table.item(row, index)
            if item is None:
                continue

            background_color = item.background()
            if background_color.color() == QtGui.QColor(199, 208, 204):
                continue

            item.setCheckState(QtCore.Qt.Checked if new_state else QtCore.Qt.Unchecked)

            if new_state:
                item.setBackground(QtGui.QColor(189, 236, 182))
            else:
                item.setBackground(QtGui.QColor(255, 255, 255))

    def on_well_checkbox_changed(self, item):
        """Обработка изменения состояния чекбокса скважины"""
        if item.row() != 0:
            return

        table = self.ui.tableWidget_sh_web_params
        checked_columns = []
        for col in range(table.columnCount()):
            well_item = table.item(0, col)
            if well_item and well_item.checkState() == QtCore.Qt.Checked:
                checked_columns.append(col)

        if len(checked_columns) == 1:
            for col in range(table.columnCount()):
                if col != checked_columns[0]:
                    other_item = table.item(0, col)
                    if other_item:
                        other_item.setCheckState(QtCore.Qt.Unchecked)

        self.update_all_items_colors()
        self.update_selected_wells_lineedit()

    def toggle_checkbox_on_click(self, row, col):
        """Переключает состояние чекбокса при клике по ячейке, даже не по самой галочке"""
        table = self.ui.tableWidget_sh_web_params
        item = table.item(row, col)
        if item is None:
            return

        if item.flags() & QtCore.Qt.ItemIsUserCheckable:
            current_state = item.checkState()
            new_state = QtCore.Qt.Unchecked if current_state == QtCore.Qt.Checked else QtCore.Qt.Checked
            item.setCheckState(new_state)
            self.update_item_color(item)



class ShWebReader(QtWidgets.QWidget, CheckboxTableMixin):
    signal_sh_web_plot_generated = QtCore.pyqtSignal(list, name='signal_sh_web_plot_generated')
    signal_sh_web_file_generated = QtCore.pyqtSignal(str, dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = self

        self.ui = Ui_ShWebReaderForm()
        self.ui.setupUi(self)

        self.init_checkbox_behavior()

        self.ui.pushButton_load_sh_web.clicked.connect(self.load_file)
        self.ui.pushButton_plot_sh_params.clicked.connect(self.plot_data)
        self.ui.pushButton_save_file.clicked.connect(self.save_file)
        self.ui.checkBox_apply_suffix.stateChanged.connect(self.update_selected_wells_lineedit)

        self.data = {}
        self.reader_counter = 0
        self.params_list = []
        self.file_names = []
        self.num_wells = []

    def load_file(self):
        paths = QtWidgets.QFileDialog.getOpenFileNames(self, "Открыть файлы из Шахматки WEB",
                                                       filter='*.xlsx *.xls')[0]
        new_paths = []
        for path in paths:
            file_name = os.path.basename(path)

            if file_name in self.file_names:
                continue

            self.file_names.append(file_name)
            self.num_wells.append(self.extract_well_number(file_name))
            new_paths.append(path)

        for path in new_paths:
            self.read_file(path)

        self.ensure_single_add_button_row()  # ⬅ здесь — только один вызов



    def read_file(self, path):
        try:
            df = pd.read_excel(path)
        except Exception as e:
            print(f'Ошибка при чтении файла: {e}')
            return

        required_columns = ['Куст']
        if any(col not in df.columns for col in required_columns):
            QtWidgets.QMessageBox.warning(self, 'Ошибка', 'Неверный формат файла.')
            return

        well_name = self.num_wells[self.reader_counter]
        self.data[well_name] = {}

        current_date = datetime.now()
        n_rows = self.count_params(path)
        total_rows = len(df)
        total_months = total_rows // n_rows

        for i in range(total_months):
            month_date = current_date.replace(day=1) if i == 0 else (month_date - timedelta(days=1)).replace(day=1)
            month_key = month_date.strftime("%m.%Y")

            row_start = 3 + i * n_rows
            row_end = row_start + n_rows
            data_block = df.iloc[row_start:row_end, 6:37]
            parameters = df.iloc[row_start:row_end, 4]

            self.data[well_name][month_key] = {
                "data": data_block,
                "parameters": parameters,
                "start_date": month_date,
                "days_in_month": monthrange(month_date.year, month_date.month)[1],
            }

            if row_start >= total_rows:
                print("row_start выходит за пределы total_rows.")
                return

        self.parameters = self.data[well_name][month_key]["parameters"].tolist()
        self.params_list.append(self.parameters)
        self.reader_counter += 1

        self.ui.lineEdit_sh_web.setText(', '.join(self.file_names))
        self.update_selected_wells_lineedit()

        self.update_params_table(self.parameters)


        self.add_button_row()  # Добавим новую строку кнопок

    def ensure_single_add_button_row(self):
        table = self.ui.tableWidget_sh_web_params

        # Удаляем все строки, где есть кнопки
        rows_to_remove = []
        for row in range(table.rowCount()):
            if any(isinstance(table.cellWidget(row, col), QtWidgets.QPushButton) for col in range(table.columnCount())):
                rows_to_remove.append(row)

        # Удаляем строки в обратном порядке, чтобы не сбивать индексы
        for row in reversed(rows_to_remove):
            table.removeRow(row)

        self.add_button_row()

    def update_params_table(self, params):
        current_row_count = self.ui.tableWidget_sh_web_params.rowCount()
        new_row_count = max(current_row_count, len(params) + 1)
        self.ui.tableWidget_sh_web_params.setRowCount(new_row_count)

        current_column_count = self.ui.tableWidget_sh_web_params.columnCount()
        new_col_index = current_column_count
        self.ui.tableWidget_sh_web_params.setColumnCount(current_column_count + 1)
        self.ui.tableWidget_sh_web_params.setHorizontalHeaderItem(new_col_index,QtWidgets.QTableWidgetItem(self.num_wells[new_col_index]))

        # Строка 0 — чекбокс для визуализации (первая строка, отвечает за активность скважины)
        well_checkbox = QtWidgets.QTableWidgetItem()
        well_checkbox = QtWidgets.QTableWidgetItem()
        # Имя скважины как заголовок
        well_checkbox.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
        well_checkbox.setCheckState(QtCore.Qt.Checked)
        well_checkbox.setBackground(QtGui.QColor(189, 236, 182))
        self.ui.tableWidget_sh_web_params.setItem(0, new_col_index, well_checkbox)



        # Строки параметров
        for row, param in enumerate(params, start=1):
            checkbox_item = QtWidgets.QTableWidgetItem(param)
            checkbox_item.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
            checkbox_item.setCheckState(QtCore.Qt.Unchecked)
            self.ui.tableWidget_sh_web_params.setItem(row, new_col_index, checkbox_item)

            month_key = next(reversed(self.data[self.num_wells[new_col_index]].keys()))
            self.mark_unavailable_params(row, new_col_index, self.num_wells[new_col_index], month_key, param)

        self.ui.tableWidget_sh_web_params.resizeColumnsToContents()
        self.ui.tableWidget_sh_web_params.update()

        #if self.reader_counter == len(self.file_names):
        #    self.add_button_row()


    def add_button_row(self):
        last_row = self.ui.tableWidget_sh_web_params.rowCount()
        self.ui.tableWidget_sh_web_params.insertRow(last_row)

        for col in range(self.ui.tableWidget_sh_web_params.columnCount()):
            add_button = QtWidgets.QPushButton('+')
            add_button.setToolTip('Добавить новый параметр')
            add_button.clicked.connect(lambda _, c=col: self.call_add_param_in_table_widget(c))
            self.ui.tableWidget_sh_web_params.setCellWidget(last_row, col, add_button)

    def call_add_param_in_table_widget(self, button):
        from mini_windows import AddParameterWindow
        button = self.sender()
        button_pos = self.ui.tableWidget_sh_web_params.indexAt(button.pos())
        col = button_pos.column()

        # 1. Получаем имя скважины
        well = self.ui.tableWidget_sh_web_params.horizontalHeaderItem(col).text()

        # 2. Получаем список параметров для этой скважины
        try:
            well_index = self.num_wells.index(well)
            raw_params = self.params_list[well_index]
        except ValueError:
            QtWidgets.QMessageBox.warning(self, "Ошибка", f"Скважина '{well}' не найдена.")
            return

        # 3. Фильтруем параметры (убираем те, где все значения NaN)
        filtered_params = []
        latest_month = next(reversed(self.data[well].keys()))
        data_block = self.data[well][latest_month]["data"]
        parameters = self.data[well][latest_month]["parameters"]

        for i, param in enumerate(parameters):
            try:
                values = data_block.iloc[i]
                if not values.isna().all():
                    filtered_params.append(param)
            except IndexError:
                continue

        # 4. Создаем param_data: имя параметра → Series с индексом-датами
        param_data = {}
        for i, param in enumerate(parameters):
            if param not in filtered_params:
                continue

            dates = []
            values = []

            for info in self.data[well].values():
                start_date = info["start_date"]
                days = info["days_in_month"]
                try:
                    vals = info["data"].iloc[i, :days].tolist()
                except IndexError:
                    continue

                dts = [start_date + timedelta(days=j) for j in range(days)]
                dates.extend(dts)
                values.extend(vals)

            if values:
                param_data[param] = pd.Series(values, index=dates)

        # 5. Запускаем окно сшивания
        self.add_param_window = AddParameterWindow(well, filtered_params, param_data)

        if self.add_param_window.exec_() == QtWidgets.QDialog.Accepted:
            new_param_name = self.add_param_window.new_param_name
            new_series = getattr(self.add_param_window, "new_param_series", None)

            if new_series is None or new_series.empty:
                QtWidgets.QMessageBox.warning(self, "Сшивание", "Сшитый параметр пуст или не задан.")
                return

            params_to_merge = self.add_param_window.params_to_merge

            # 1. Добавим в параметры
            if well in self.data:
                for month_key, month_data in self.data[well].items():
                    start = month_data["start_date"]
                    end = start + timedelta(days=month_data["days_in_month"] - 1)

                    mask = (new_series.index >= start) & (new_series.index <= end)
                    values = new_series.loc[mask].values

                    if len(values) > 0:
                        if new_param_name not in month_data["parameters"].tolist():
                            month_data["parameters"] = pd.concat([
                                month_data["parameters"],
                                pd.Series([new_param_name])
                            ]).reset_index(drop=True)

                        param_index = month_data["parameters"].tolist().index(new_param_name)

                        # Убедимся, что data содержит нужное количество строк
                        if len(month_data["data"]) <= param_index:
                            pad = param_index + 1 - len(month_data["data"])
                            month_data["data"] = pd.concat([
                                month_data["data"],
                                pd.DataFrame([[None] * month_data["data"].shape[1]] * pad)
                            ], ignore_index=True)

                        n = min(len(values), month_data["data"].shape[1])
                        month_data["data"].iloc[param_index, :n] = values[:n]

            # 2. Добавим визуально в таблицу
            insert_row = self.ui.tableWidget_sh_web_params.rowCount() - 1
            self.ui.tableWidget_sh_web_params.insertRow(insert_row)

            chkBoxItem = QtWidgets.QTableWidgetItem(new_param_name)
            chkBoxItem.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
            chkBoxItem.setCheckState(QtCore.Qt.Checked)
            self.ui.tableWidget_sh_web_params.setItem(insert_row, col, chkBoxItem)

            # 3. Обновляем списки
            if well in self.num_wells:
                well_index = self.num_wells.index(well)
                if new_param_name not in self.params_list[well_index]:
                    self.params_list[well_index].append(new_param_name)

            self.ui.tableWidget_sh_web_params.update()

            # 4. Обновляем графики при наличии
            if hasattr(self, 'update_plot'):
                self.update_plot()

    def update_selected_wells_lineedit(self):
        wells_with_suffix = []
        for col in range(self.ui.tableWidget_sh_web_params.columnCount()):
            item = self.ui.tableWidget_sh_web_params.item(0, col)
            if item is not None and item.checkState() == QtCore.Qt.Checked:
                well = self.num_wells[col]
                if self.ui.checkBox_apply_suffix.isChecked():
                    well += self.ui.lineEdit_wells_suffix.text()
                wells_with_suffix.append(well)
        self.ui.lineEdit_well_name_sh_web.setText(', '.join(wells_with_suffix))

    def mark_unavailable_params(self, row, col, well_num, month_key, param):
        try:
            data_block = self.data[well_num][month_key]["data"]
            param_index = self.data[well_num][month_key]["parameters"].tolist().index(param)
            param_data = data_block.iloc[param_index]

            if param_data.isna().all():
                item = self.ui.tableWidget_sh_web_params.item(row, col)
                if item:
                    text = item.text()
                    new_item = QtWidgets.QTableWidgetItem(text)
                    new_item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
                    new_item.setBackground(QtGui.QColor(199, 208, 204))
                    new_item.setForeground(QtGui.QColor(100, 100, 100))
                    self.ui.tableWidget_sh_web_params.setItem(row, col, new_item)
        except (KeyError, ValueError):
            pass

    def add_new_param_to_main_df(self, well, params_to_merge, new_param_name):
        """
        Добавляет новый сшитый параметр в основную структуру данных
        """
        if well not in self.data:
            return

        # Собираем данные для нового параметра
        merged_series = None
        for param in params_to_merge:
            for month_key in self.data[well]:
                if param in self.data[well][month_key]["parameters"].tolist():
                    param_index = self.data[well][month_key]["parameters"].tolist().index(param)
                    param_data = self.data[well][month_key]["data"].iloc[param_index]

                    # Создаем временной ряд для параметра
                    dates = [self.data[well][month_key]["start_date"] + timedelta(days=i)
                             for i in range(self.data[well][month_key]["days_in_month"])]
                    series = pd.Series(param_data.values[:len(dates)], index=dates)

                    if merged_series is None:
                        merged_series = series
                    else:
                        merged_series = pd.concat([merged_series, series]).sort_index()

        if merged_series is not None:
            # Добавляем новый параметр в каждый месяц
            for month_key in self.data[well]:
                month_data = self.data[well][month_key]
                start_date = month_data["start_date"]
                end_date = start_date + timedelta(days=month_data["days_in_month"] - 1)

                # Фильтруем данные для текущего месяца
                month_mask = (merged_series.index >= start_date) & (merged_series.index <= end_date)
                month_values = merged_series[month_mask].values

                if len(month_values) > 0:
                    # Добавляем параметр в список параметров (если еще не добавлен)
                    if new_param_name not in month_data["parameters"].tolist():
                        month_data["parameters"] = pd.concat([
                            month_data["parameters"],
                            pd.Series([new_param_name])
                        ]).reset_index(drop=True)

                    # Добавляем данные
                    param_index = month_data["parameters"].tolist().index(new_param_name)
                    if len(month_data["data"]) <= param_index:
                        # Если нужно расширить DataFrame
                        month_data["data"] = pd.concat([
                            month_data["data"],
                            pd.DataFrame([[None] * 31])
                        ], ignore_index=True)

                    month_data["data"].iloc[param_index, :len(month_values)] = month_values

    def count_params(self, file_path):
        workbook = openpyxl.load_workbook(file_path)
        sheet = workbook.active

        current_month = None
        parameter_count = {}
        for row in sheet.iter_rows(min_row=5, max_col=5, values_only=True):
            _, month, _, _, parameter = row
            if month is not None and month != current_month:
                current_month = month
                parameter_count[current_month] = 0
            if parameter is not None:
                parameter_count[current_month] += 1

        return list(parameter_count.values())[-1]

    def extract_well_number(self, filename):
        start_index = filename.find("скв.")
        if start_index == -1:
            return None
        substring = filename[start_index:]
        bracket_index = substring.find('(')
        if bracket_index != -1:
            substring = substring[:bracket_index]
        return substring.replace("скв.", "").strip()

    def plot_data(self):
        from matplotlib import pyplot as plt
        import matplotlib.patches as mpatches
        from datetime import timedelta
        import pandas as pd

        table = self.ui.tableWidget_sh_web_params
        self.legend_patch_map = {}

        pressure_params = {
            "Рзаб огр инд", "Pзат после шт", "Pзат до шт", "Pкуст", "Pзаб (иссл.)", "Pпл кр.",
            "Pзаб(PпрTM)", "Рзат ТМ", "Рзаб(цнгд)", "Рзатр стат", "Pзаб(Hд)",
            "Рприем", "Рзатр", "Рст", "Рбуф ТМ", "Pзаб(цднг)", "Рбуф"
        }
        volume_group = {"Qж", "Qж(тн)", "Qприем"}

        selected_params = {
            table.item(row, col).text()
            for row in range(1, table.rowCount())
            for col in range(table.columnCount())
            if (
                    (item := table.item(row, col)) and
                    item.checkState() == QtCore.Qt.Checked and
                    item.text().strip().lower() != "примечание"
            )
        }

        if not selected_params:
            QtWidgets.QMessageBox.warning(self, "Ошибка", "Не выбран ни один параметр.")
            return

        active_wells = [
            (self.num_wells[col], col)
            for col in range(table.columnCount())
            if (header_item := table.item(0, col)) and header_item.checkState() == QtCore.Qt.Checked
        ]

        if not active_wells:
            QtWidgets.QMessageBox.warning(self, "Ошибка", "Не выбрана ни одна скважина.")
            return

        if hasattr(self, 'fig') and self.fig:
            plt.close(self.fig)  # Закрыть предыдущую фигуру, если есть
        self.fig = plt.figure(constrained_layout=True, figsize=(12, 5 * len(active_wells)))
        fig = self.fig
        colors = ['b', 'c', 'm', 'y', 'r', 'g', 'k', 'orange']
        left, width, height, v_space = 0.07, 0.45, 0.18, 0.06
        active_dates_by_param = {param: set() for param in selected_params}
        has_plots = False

        for idx, (well, col) in enumerate(active_wells):
            available_params = self.params_list[col]
            bottom = 1.0 - (idx + 1) * (height + v_space)
            ax_main = fig.add_axes([left, bottom, width, height])

            group_axes = {}
            volume_ax = None
            param_index = 0

            for param in selected_params:
                if param not in available_params:
                    continue

                row = available_params.index(param)
                dates, values = [], []

                for info in self.data[well].values():
                    start_date = info["start_date"]
                    days = info["days_in_month"]
                    vals = info["data"].iloc[row, :days].tolist()
                    dts = [start_date + timedelta(days=i) for i in range(days)]

                    for d, v in zip(dts, vals):
                        if isinstance(v, (int, float)) and not pd.isna(v):
                            active_dates_by_param[param].add(d)

                    dates.extend(dts)
                    values.extend(vals)

                if not values:
                    continue

                param_fixed_colors = {
                    **{p: 'r' for p in selected_params if p.startswith('P') or p.startswith('Р')},
                    'Qн': 'darkseagreen',
                    'Qн(тн)': 'darkseagreen',
                    'Qж': 'g',
                    'Qж(тн)': 'purple'
                }

                color = param_fixed_colors.get(param, colors[param_index % len(colors)])
                patch = mpatches.Patch(color=color, label=param)
                label = f"{well}_{param}"

                if param_index == 0:
                    line, = ax_main.plot(dates, values, '.', color=color, label=label)
                    ax_main.set_ylabel(param)
                    legend_ax = ax_main.legend(handles=[patch], loc='upper left', bbox_to_anchor=(0.0, 1.15),
                                               frameon=False, fontsize=8)
                else:
                    if param in volume_group:
                        if volume_ax is None:
                            volume_ax = ax_main.twinx()
                            volume_ax.spines["right"].set_position(("outward", 75 * len(group_axes)))
                            volume_ax.set_ylabel("Объемы")
                            group_axes["volume"] = volume_ax
                        ax = volume_ax
                    else:
                        ax = ax_main.twinx()
                        ax.spines['right'].set_position(('outward', 75 * len(group_axes)))
                        ax.set_ylabel(param)
                        group_axes[param] = ax

                    line, = ax.plot(dates, values, '.', color=color, label=label)
                    legend_ax = ax.legend(handles=[patch], loc='upper left',
                                          bbox_to_anchor=(param_index * 0.15, 1.15), frameon=False, fontsize=8)

                for patch_item in legend_ax.get_patches():
                    patch_item.set_picker(5)
                    self.legend_patch_map[patch_item] = line

                for scatter in ax_main.collections:
                    scatter.set_picker(True)

                param_index += 1

            if param_index == 0:
                ax_main.set_visible(False)
                continue

            ax_main.set_title(f"{well}", pad=30)
            ax_main.set_xlabel("Дата")
            ax_main.grid(True)
            ax_main.tick_params(labelbottom=True, axis='x', rotation=45)
            has_plots = True

        if not has_plots:
            QtWidgets.QMessageBox.warning(self, "Ошибка", "Нет данных для построения графиков.")
            return

        print("Активные даты по параметрам:")
        for param, dates in active_dates_by_param.items():
            if dates:
                sorted_dates = sorted(dates)
                print(f"{param}: {len(sorted_dates)} дней, {sorted_dates[0].date()} — {sorted_dates[-1].date()}")
            else:
                print(f"{param}: нет активных данных")

        # Функция для обработки кликов на патчах
        def on_pick(event):
            artist = event.artist
            print(f"[DEBUG] Клик по объекту: {artist}")
            if isinstance(artist, mpatches.Patch):  # Проверка, что это патч
                if artist in self.legend_patch_map:
                    line = self.legend_patch_map[artist]
                    print(f"[DEBUG] Найдена связанная линия: {line.get_label()}, видимость до: {line.get_visible()}")
                    visible = not line.get_visible()
                    line.set_visible(visible)
                    artist.set_alpha(1.0 if visible else 0.2)
                    fig.canvas.draw_idle()
                else:
                    print("[DEBUG] Патч не найден в legend_patch_map.")
            else:
                print("[DEBUG] Клик не по патчу")

            # Перерисовываем график после изменения видимости
            plt.draw()

        # Подключаем функцию к событию pick_event
        self.fig.canvas.mpl_connect('pick_event', on_pick)

        if has_plots:
            plt.show()

            # если используется сигнал (например, для вставки в интерфейс)
            self.fig, _ = plt.subplots(constrained_layout=True)
            canvas = FigureCanvas(self.fig)
            self.signal_sh_web_plot_generated.emit([canvas])
        else:
            QtWidgets.QMessageBox.warning(self, "Нет данных", "Все выбранные параметры оказались пустыми.")




    def save_file(self):

        self.get_checked_data()

        selected_wells_params = {}
        column_count = self.ui.tableWidget_sh_web_params.columnCount()

        for well, self.sub_gr in self.select_subdf.items():

            column_index = -1
            for col in range(column_count):
                header_item = self.ui.tableWidget_sh_web_params.horizontalHeaderItem(col)
                if header_item is not None and header_item.text() == well:
                    column_index = col
                    break

            selected_parameters = []
            for row in range(1, self.ui.tableWidget_sh_web_params.rowCount()):
                checkbox_item = self.ui.tableWidget_sh_web_params.item(row, column_index)
                if checkbox_item is not None and checkbox_item.checkState() == QtCore.Qt.Checked:
                    parameter = self.ui.tableWidget_sh_web_params.item(row, column_index).text()
                    selected_parameters.append(parameter)

            if selected_parameters:
                well_name = self.ui.tableWidget_sh_web_params.horizontalHeaderItem(column_index).text()
                selected_wells_params[well_name] = selected_parameters

            if not selected_wells_params:
                QtWidgets.QMessageBox.warning(self, "Ошибка", "Выберите хотя бы один параметр для сохранения")
                return

        self.parameter_selection_window = ParameterSelectionWindow(selected_wells_params)
        self.parameter_selection_window.show()

        if self.parameter_selection_window.exec_() == QtWidgets.QMessageBox.Accepted:
            self.selected_parameters = self.parameter_selection_window.selected_parameters
            self.select_directory_and_save()

    def select_directory_and_save(self):
        from PyQt5.QtWidgets import QFileDialog, QMessageBox
        from datetime import datetime

        g = 9.81  # ускорение свободного падения
        dfs = []
        column_count = self.ui.tableWidget_sh_web_params.columnCount()

        num = 0
        for well, self.sub_gr in self.select_subdf.items():

            column_index = -1
            for col in range(column_count):
                header_item = self.ui.tableWidget_sh_web_params.horizontalHeaderItem(col)
                if header_item is not None and header_item.text() == well:
                    column_index = col
                    break

            selected_parameters_for_saving = []
            for row in range(1, self.ui.tableWidget_sh_web_params.rowCount()):
                checkbox_item = self.ui.tableWidget_sh_web_params.item(row, column_index)
                if checkbox_item is not None and checkbox_item.checkState() == QtCore.Qt.Checked:
                    parameter = checkbox_item.text()
                    selected_parameters_for_saving.append(parameter)

            all_data = []
            for parameter in selected_parameters_for_saving:

                all_dates = self.sub_gr['Дата']
                all_values = []

                data_row = self.sub_gr[parameter]
                data_row = data_row.replace(',', '.', regex=True).astype(float)

                all_values.extend(data_row)

                # Гидростатическое давление или пересчёт массы в объём — при необходимости
                if well in self.selected_parameters and parameter in self.selected_parameters[well]:
                    param_info = self.selected_parameters[well][parameter]

                    if isinstance(param_info, dict) and 'density' in param_info and 'tvd' in param_info:
                        density = float(param_info['density'])
                        tvd = float(param_info['tvd'])
                        sign = float(str(param_info.get('sign', 1)))
                        hydrostatic_pressure = sign * density * g * tvd * 0.00001

                        if "+" in parameter and "буф" in parameter:
                            mask = self.sub_gr['Рбуф'].notna()
                            self.sub_gr.loc[mask, parameter] = pd.to_numeric(self.sub_gr.loc[mask, parameter],
                                                                             errors='coerce')
                            self.sub_gr.loc[mask, parameter] += hydrostatic_pressure
                            all_values = self.sub_gr[parameter].tolist()
                        else:
                            all_values = [value + hydrostatic_pressure for value in all_values]

                    if isinstance(param_info,
                                  dict) and 'rho' in param_info and 'rho_unit' in param_info and 'B' in param_info:
                        rho = float(param_info['rho'])
                        rho_unit = param_info['rho_unit']
                        B = float(param_info['B'])
                        m_to_v_coeff = 1000 if rho_unit == 'кг/м³' else 1
                        all_values = [m / rho * B * m_to_v_coeff for m in all_values]

                all_data.append(pd.DataFrame({"Time": all_dates, parameter: all_values}))

            if not all_data:
                continue

            df_to_save = all_data[0]
            for df in all_data[1:]:
                df_to_save = pd.merge(df_to_save, df, on="Time", how="outer")

            df_to_save = df_to_save.sort_values(by="Time")
            df_to_save["Time"] = df_to_save["Time"].dt.strftime("%d.%m.%Y")

            well_names_text = self.ui.lineEdit_well_name_sh_web.text()
            well_names_list = [name.strip() for name in well_names_text.split(',')]

            if num < len(well_names_list):
                df_to_save.insert(0, 'num', well_names_list[num])
            else:
                df_to_save.insert(0, 'num', well)

            dfs.append(df_to_save)
            num += 1

        if not dfs:
            QMessageBox.warning(self, "Нет данных", "Не найдено данных для сохранения.")
            return

        df_result = pd.concat(dfs, ignore_index=True)
        df_result['Time'] = pd.to_datetime(df_result['Time'], format='%d.%m.%Y')
        df_result.sort_values(by=['num', 'Time'], inplace=True)
        df_result.reset_index(drop=True, inplace=True)

        save_path = QFileDialog.getExistingDirectory(self, 'Выберите директорию')
        if save_path:
            file_name = 'from_sh_web'
            date_time = datetime.now().strftime("%d_%m_%Y_%H_%M_%S")
            xlsx_file_path = os.path.join(save_path, f'{file_name}_{date_time}.xlsx')

            with pd.ExcelWriter(xlsx_file_path) as writer:
                df_result.to_excel(writer, index=False)
                QMessageBox.information(None, "Успех", "Данные успешно сохранены")

            self.signal_sh_web_file_generated.emit(xlsx_file_path, self.selected_parameters)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = ShWebReader()
    window.show()
    sys.exit(app.exec())


   





