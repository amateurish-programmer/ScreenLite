"""Shared quiet, high-contrast desktop palette."""

STYLE = """
QWidget { font-family: 'Microsoft YaHei UI', 'Segoe UI'; font-size: 13px; color: #203334; }
QMainWindow, QDialog { background: #F7F8F5; }
QLabel { background: transparent; }
QLabel#eyebrow { color: #087F75; font-weight: 700; font-size: 12px; }
QLabel#title { font-size: 30px; font-weight: 700; }
QLabel#muted { color: #687876; }
QLabel#preview { background: #E8EEEA; border: 1px solid #DCE4DE; border-radius: 12px; }
QPushButton { background: #FFFFFF; border: 1px solid #D9E1DC; border-radius: 9px; padding: 10px 16px; }
QPushButton:hover { background: #EAF3EE; border-color: #A9C7BA; }
QPushButton:pressed { background: #DCEBE3; }
QPushButton:disabled { color: #9BA5A0; background: #EEF0EB; }
QPushButton#primary { background: #087F75; color: white; border: 1px solid #087F75; font-weight: 600; }
QPushButton#primary:hover { background: #096D66; }
QPushButton#danger { color: #AF3F35; background: #FFF0EB; border-color: #E8B9AE; }
QComboBox, QSpinBox, QLineEdit, QKeySequenceEdit { background: white; border: 1px solid #D9E1DC; border-radius: 6px; padding: 7px; min-height: 20px; }
QComboBox QAbstractItemView { background: white; selection-background-color: #DCEEE5; color: #203334; }
QProgressBar { border: 0; border-radius: 5px; background: #E2E9E3; text-align: center; min-height: 8px; }
QProgressBar::chunk { border-radius: 5px; background: #087F75; }
QToolTip { background: #203334; color: white; border: 0; padding: 6px; }
"""
