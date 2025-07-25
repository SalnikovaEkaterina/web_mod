from PyQt5.QtWidgets import (
    QDialog, QLabel, QPushButton, QCalendarWidget,
    QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QSizePolicy, QFrame, QSpacerItem, QMessageBox
)
from PyQt5.QtCore import Qt, QDate


class DateRangeApp(QDialog):
    def __init__(self, available_dates=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Выбор даты")
        self.setMinimumWidth(500)

        self.available_dates = available_dates or []
        self.date_ranges = []
        self.current_range = [None, None]
        self.editing_index = -1

        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)

        # Верхняя часть с выбором дат
        top_frame = QFrame()
        top_layout = QHBoxLayout(top_frame)

        date_label = QLabel("Дата")
        top_layout.addWidget(date_label)

        self.date_btn1 = QPushButton("01.01.2024")
        self.date_btn1.clicked.connect(lambda: self.showCalendar(0))

        self.date_btn2 = QPushButton("01.01.2025")
        self.date_btn2.clicked.connect(lambda: self.showCalendar(1))

        self.date_btn1.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.date_btn2.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        top_layout.addWidget(self.date_btn1)
        top_layout.addWidget(self.date_btn2)
        top_layout.setSpacing(5)

        layout.addWidget(top_frame)

        # Таблица отрезков
        self.ranges_table = QTableWidget()
        self.ranges_table.setColumnCount(2)
        self.ranges_table.setHorizontalHeaderLabels(["Начало", "Конец"])
        self.ranges_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.ranges_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.ranges_table.verticalHeader().setVisible(False)
        self.ranges_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.ranges_table.cellDoubleClicked.connect(self.editRange)

        layout.addWidget(self.ranges_table, stretch=1)

        # Кнопки снизу
        btn_frame = QFrame()
        btn_layout = QHBoxLayout(btn_frame)

        btn_layout.addItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        self.cancel_btn = QPushButton("Отмена")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.add_range_btn = QPushButton("Добавить промежуток")
        self.add_range_btn.clicked.connect(self.addAnotherRange)
        btn_layout.addWidget(self.add_range_btn)

        self.save_btn = QPushButton("Сохранить")
        self.save_btn.clicked.connect(self.saveAndClose)
        btn_layout.addWidget(self.save_btn)

        btn_layout.addItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        layout.addWidget(btn_frame)
        self.setLayout(layout)

    def showCalendar(self, index):
        calendar_dialog = CalendarDialog(parent=self, available_dates=self.available_dates)
        if calendar_dialog.exec_():
            selected_date = calendar_dialog.selected_date
            if selected_date is not None:
                self.current_range[index] = selected_date
                if index == 0:
                    self.date_btn1.setText(selected_date.toString("dd.MM.yyyy"))
                else:
                    self.date_btn2.setText(selected_date.toString("dd.MM.yyyy"))

    def addRange(self):
        if not self.current_range[0] or not self.current_range[1]:
            QMessageBox.warning(self, "Ошибка", "Пожалуйста, выберите обе даты.")
            return

        if self.current_range[0] > self.current_range[1]:
            QMessageBox.warning(self, "Ошибка", "Дата начала не может быть позже даты окончания.")
            return

        if self.editing_index >= 0:
            self.date_ranges[self.editing_index] = (self.current_range[0], self.current_range[1])
            self.editing_index = -1
        else:
            self.date_ranges.append((self.current_range[0], self.current_range[1]))

        self.updateRangesTable()

    def addAnotherRange(self):
        self.addRange()
        self.resetCurrentRange()

    def resetCurrentRange(self):
        self.current_range = [None, None]
        self.date_btn1.setText("01.01.2000")
        self.date_btn2.setText("01.01.2000")

    def updateRangesTable(self):
        self.ranges_table.setRowCount(len(self.date_ranges))
        for i, (start, end) in enumerate(self.date_ranges):
            self.ranges_table.setItem(i, 0, QTableWidgetItem(start.toString("dd.MM.yyyy")))
            self.ranges_table.setItem(i, 1, QTableWidgetItem(end.toString("dd.MM.yyyy")))
        self.ranges_table.resizeRowsToContents()
        self.adjustSize()

    def editRange(self, row, column):
        if row < len(self.date_ranges):
            self.editing_index = row
            start_date, end_date = self.date_ranges[row]
            self.current_range = [start_date, end_date]
            self.date_btn1.setText(start_date.toString("dd.MM.yyyy"))
            self.date_btn2.setText(end_date.toString("dd.MM.yyyy"))
            self.date_ranges.pop(row)
            self.updateRangesTable()
            QMessageBox.information(self, "Редактирование", "Измените даты и нажмите 'Добавить промежуток'.")

    def get_selected_ranges(self):
        from pandas import Timestamp
        return [(Timestamp(start.toPyDate()), Timestamp(end.toPyDate())) for start, end in self.date_ranges]

    def get_formatted_ranges(self):
        return ", ".join(
            f"{start.toString('dd.MM.yyyy')}-{end.toString('dd.MM.yyyy')}"
            for start, end in self.date_ranges
        )

    def saveAndClose(self):
        self.addRange()  # Добавим текущий диапазон, если он был выбран
        if not self.date_ranges:
            QMessageBox.warning(self, "Ошибка", "Нет выбранных диапазонов.")
            return
        self.accept()


class CalendarDialog(QDialog):
    def __init__(self, parent=None, available_dates=None):
        super().__init__(parent)
        self.setWindowTitle("Календарь")
        self.setModal(True)
        self.selected_date = None
        self.available_dates = available_dates or []
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)

        if self.available_dates:
            min_d = min(self.available_dates)
            max_d = max(self.available_dates)
            self.calendar.setMinimumDate(QDate(min_d.year, min_d.month, min_d.day))
            self.calendar.setMaximumDate(QDate(max_d.year, max_d.month, max_d.day))
        else:
            self.calendar.setMinimumDate(QDate(1900, 1, 1))
            self.calendar.setMaximumDate(QDate(2200, 1, 1))

        layout.addWidget(self.calendar)

        btn_layout = QHBoxLayout()

        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.confirm_date)  # <-- вместо self.accept

        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def confirm_date(self):
        self.selected_date = self.calendar.selectedDate()
        self.accept()



