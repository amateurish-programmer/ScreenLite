import pytest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtWidgets import QApplication

from screenlite.ui.selection import SelectionOverlay


def make_overlay(qtbot, scale=1.0, mode='capture', patterned=False):
    image = QImage(800, 600, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.white)
    if patterned:
        for y in range(image.height()):
            for x in range(image.width()):
                image.setPixelColor(x, y, QColor(x % 256, y % 256, (x * 17 + y * 13) % 256))
    pixmap = QPixmap.fromImage(image)
    pixmap.setDevicePixelRatio(scale)
    widget = SelectionOverlay(QApplication.primaryScreen(), pixmap, mode)
    widget.resize(round(800 / scale), round(600 / scale))
    qtbot.addWidget(widget)
    widget.show()
    widget.selection = QRect(30, 30, 220, 160)
    widget._position_toolbar()
    return widget


def draw(qtbot, widget, start, end):
    qtbot.mousePress(widget, Qt.MouseButton.LeftButton, pos=QPoint(*start))
    qtbot.mouseMove(widget, QPoint(*end))
    qtbot.mouseRelease(widget, Qt.MouseButton.LeftButton, pos=QPoint(*end))


@pytest.mark.parametrize('tool', ['rectangle', 'ellipse', 'arrow', 'pen'])
def test_drawing_exports_pixels_and_undo_redo(qtbot, tool):
    widget = make_overlay(qtbot)
    baseline = widget.render_selection()
    widget.set_tool(tool)
    draw(qtbot, widget, (70, 70), (180, 140))
    annotated = widget.render_selection()
    assert annotated != baseline
    assert widget.selection == QRect(30, 30, 220, 160)
    assert annotated.pixelColor(0, 0) == QColor('white')
    widget.undo()
    assert widget.render_selection() == baseline
    widget.redo()
    assert widget.render_selection() == annotated


def test_mosaic_only_changes_dragged_region_and_redo_restores_it(qtbot):
    widget = make_overlay(qtbot, patterned=True)
    baseline = widget.render_selection()
    widget.set_tool('mosaic')
    draw(qtbot, widget, (60, 60), (180, 140))
    result = widget.render_selection()
    assert result != baseline
    assert result.pixelColor(5, 5) == baseline.pixelColor(5, 5)
    assert result.pixelColor(35, 35) == result.pixelColor(36, 35)
    widget.undo()
    assert widget.render_selection() == baseline
    widget.redo()
    assert widget.render_selection() == result


def test_chinese_text_commit_cancel_and_final_confirm(qtbot):
    widget = make_overlay(qtbot)
    baseline = widget.render_selection()
    widget.set_tool('text')
    qtbot.mouseClick(widget, Qt.MouseButton.LeftButton, pos=QPoint(60, 60))
    widget.text_editor.setText('中文标注')
    qtbot.keyClick(widget.text_editor, Qt.Key.Key_Escape)
    assert widget.render_selection() == baseline
    assert not widget._completed
    qtbot.mouseClick(widget, Qt.MouseButton.LeftButton, pos=QPoint(60, 60))
    widget.text_editor.setText('中文标注')
    qtbot.keyClick(widget.text_editor, Qt.Key.Key_Return)
    assert not widget._completed
    assert widget.render_selection() != baseline
    widget.undo()
    assert widget.render_selection() == baseline
    qtbot.mouseClick(widget, Qt.MouseButton.LeftButton, pos=QPoint(60, 60))
    widget.text_editor.setText('确认保存文字')
    with qtbot.waitSignal(widget.selected):
        qtbot.mouseClick(widget.confirm_button, Qt.MouseButton.LeftButton)
    assert widget.render_selection() != baseline


@pytest.mark.parametrize('scale', [1.25, 1.5])
def test_export_uses_physical_crop_and_annotation_scale(qtbot, scale):
    widget = make_overlay(qtbot, scale, patterned=True)
    widget.selection = QRect(31, 33, 121, 103)
    result = widget.render_selection()
    assert result.devicePixelRatio() == 1
    assert (result.width(), result.height()) == (round(121 * scale), round(103 * scale))
    source = widget.pixmap.toImage()
    assert result.pixelColor(0, 0) == source.pixelColor(round(31 * scale), round(33 * scale))
    widget.set_tool('rectangle')
    draw(qtbot, widget, (50, 50), (100, 100))
    annotated = widget.render_selection()
    assert annotated.pixelColor(round(50 * scale) - round(31 * scale),
                                round(70 * scale) - round(33 * scale)).red() > 180
    assert annotated != result


@pytest.mark.parametrize('mode', ['capture', 'record'])
def test_toolbar_follows_selection_and_stays_inside_edges(qtbot, mode):
    widget = make_overlay(qtbot, mode=mode)
    first = widget.toolbar.geometry()
    assert first.top() > widget.selection.bottom()
    widget.selection.translate(130, 30)
    widget._position_toolbar()
    assert widget.toolbar.y() == first.y() + 30
    assert widget.toolbar.x() >= first.x()
    widget.selection = QRect(500, 470, 290, 120)
    widget._position_toolbar()
    assert widget.toolbar.geometry().bottom() < widget.selection.top()
    assert widget.rect().contains(widget.toolbar.geometry())
    widget.selection = widget.rect()
    widget._position_toolbar()
    assert widget.rect().contains(widget.toolbar.geometry())
    assert widget.hint_label.y() > widget.confirm_button.y()
    if mode == 'record':
        assert not widget.tool_buttons
        widget.set_tool('rectangle')
        assert widget.tool == 'select'


def test_selection_mode_preserves_handles_and_release_clears_images(qtbot):
    widget = make_overlay(qtbot)
    widget.set_tool('rectangle')
    draw(qtbot, widget, (60, 60), (110, 110))
    widget.set_tool('select')
    draw(qtbot, widget, (100, 100), (110, 110))
    assert widget.selection == QRect(40, 40, 220, 160)
    draw(qtbot, widget, (260, 200), (280, 210))
    assert widget.selection == QRect(40, 40, 240, 170)
    widget.release_resources()
    widget.release_resources()
    assert widget.pixmap.isNull()
    assert widget.render_selection().isNull()

@pytest.mark.parametrize('end', [(180, 70), (70, 140)])
def test_axis_aligned_arrow_is_not_discarded(qtbot, end):
    widget = make_overlay(qtbot)
    baseline = widget.render_selection()
    widget.set_tool('arrow')
    draw(qtbot, widget, (70, 70), end)
    assert widget.render_selection() != baseline


def test_color_width_controls_and_new_stroke_clear_redo(qtbot):
    widget = make_overlay(qtbot)
    widget.set_tool('rectangle')
    qtbot.mouseClick(widget.color_buttons['#50a5ff'], Qt.MouseButton.LeftButton)
    widget.width_combo.setCurrentIndex(2)
    draw(qtbot, widget, (70, 70), (180, 140))
    result = widget.render_selection()
    assert result.pixelColor(40, 60) == QColor('#50a5ff')
    assert result.pixelColor(42, 60) == QColor('#50a5ff')
    widget.undo()
    widget.set_tool('pen')
    draw(qtbot, widget, (90, 90), (160, 100))
    result = widget.render_selection()
    widget.redo()
    assert widget.render_selection() == result


def test_ime_committed_text_is_exported(qtbot):
    from PySide6.QtGui import QInputMethodEvent
    widget = make_overlay(qtbot)
    baseline = widget.render_selection()
    widget.set_tool('text')
    qtbot.mouseClick(widget, Qt.MouseButton.LeftButton, pos=QPoint(60, 60))
    event = QInputMethodEvent()
    event.setCommitString('中文输入')
    QApplication.sendEvent(widget.text_editor, event)
    qtbot.keyClick(widget.text_editor, Qt.Key.Key_Return)
    assert widget.render_selection() != baseline


def test_toolbar_resizes_to_narrow_viewport(qtbot):
    widget = make_overlay(qtbot)
    widget.resize(320, 300)
    widget.selection = QRect(10, 10, 290, 260)
    widget._position_toolbar()
    assert widget.rect().contains(widget.toolbar.geometry())
    assert widget.toolbar.rect().contains(widget.confirm_button.geometry())
    assert widget.hint_label.geometry().bottom() < widget.toolbar.height()


def _contrast_ratio(first, second):
    def luminance(color):
        rgb = [channel / 255 for channel in (color.red(), color.green(), color.blue())]
        linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
                  for value in rgb]
        return sum(component * weight for component, weight in zip(linear, (0.2126, 0.7152, 0.0722)))
    values = sorted((luminance(first), luminance(second)))
    return (values[1] + 0.05) / (values[0] + 0.05)


@pytest.mark.parametrize('color', ['#ff4d58', '#ffd45c', '#50dc9b', '#50a5ff', '#ffffff', '#202020'])
def test_text_editor_palette_stays_readable(qtbot, color):
    from PySide6.QtGui import QPalette
    widget = make_overlay(qtbot)
    widget.set_tool('text')
    qtbot.mouseClick(widget.color_buttons[color], Qt.MouseButton.LeftButton)
    qtbot.mouseClick(widget, Qt.MouseButton.LeftButton, pos=QPoint(60, 60))
    widget.text_editor.setText('可读文字')
    widget.text_editor.ensurePolished()
    image = widget.text_editor.grab().toImage()
    foreground = widget.text_editor.palette().color(QPalette.ColorRole.Text)
    background = image.pixelColor(image.width() - 5, image.height() // 2)
    assert foreground == QColor(color)
    assert _contrast_ratio(foreground, background) >= 4.5


def test_active_text_preview_updates_with_color_and_width(qtbot):
    from PySide6.QtGui import QPalette
    widget = make_overlay(qtbot)
    widget.set_tool('text')
    qtbot.mouseClick(widget.color_buttons['#ffffff'], Qt.MouseButton.LeftButton)
    qtbot.mouseClick(widget, Qt.MouseButton.LeftButton, pos=QPoint(60, 60))
    editor = widget.text_editor
    editor.setText('保留输入')
    qtbot.mouseClick(widget.color_buttons['#ff4d58'], Qt.MouseButton.LeftButton)
    widget.width_combo.setCurrentIndex(3)
    editor.ensurePolished()
    assert widget.text_editor is editor
    assert editor.text() == '保留输入'
    assert editor.palette().color(QPalette.ColorRole.Text) == QColor('#ff4d58')
    assert editor.font().pixelSize() == 44
    assert editor.height() > 44
    qtbot.keyClick(editor, Qt.Key.Key_Return)
    assert widget.annotations[-1].color == QColor('#ff4d58')
    assert widget.annotations[-1].width == 10
