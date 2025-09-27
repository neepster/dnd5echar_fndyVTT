from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

from PySide6 import QtCore, QtGui, QtWidgets

from ..constants import ABILITY_NAMES, ABILITY_SCORES, SKILL_NAMES, SKILL_TO_ABILITY
from ..data import SRDData
from ..models import CharacterState
from ..state import CharacterViewModel, ChoiceGroup


class ChoiceGroupWidget(QtWidgets.QGroupBox):
    selectionChanged = QtCore.Signal(str, list)

    def __init__(self, group: ChoiceGroup, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(group.name, parent)
        self.group = group
        self.list_widget = QtWidgets.QListWidget(self)
        self.list_widget.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.list_widget.itemChanged.connect(self._on_item_changed)

        description = QtWidgets.QLabel(group.description or "")
        description.setWordWrap(True)
        description.setVisible(bool(group.description))

        layout = QtWidgets.QVBoxLayout(self)
        if description.isVisible():
            layout.addWidget(description)
        layout.addWidget(self.list_widget)

        for option in group.options:
            item = QtWidgets.QListWidgetItem(option.label)
            item.setData(QtCore.Qt.UserRole, option.id)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.Unchecked)
            self.list_widget.addItem(item)
        self.setTitle(f"{group.name} (choose {group.choose})")

    def set_selected(self, selected: Iterable[str]) -> None:
        selected_set = {sid.lower() for sid in selected}
        with QtCore.QSignalBlocker(self.list_widget):
            for index in range(self.list_widget.count()):
                item = self.list_widget.item(index)
                opt_id = str(item.data(QtCore.Qt.UserRole)).lower()
                item.setCheckState(QtCore.Qt.Checked if opt_id in selected_set else QtCore.Qt.Unchecked)

    def _on_item_changed(self, item: QtWidgets.QListWidgetItem) -> None:
        checked_items: List[str] = []
        for index in range(self.list_widget.count()):
            candidate = self.list_widget.item(index)
            if candidate.checkState() == QtCore.Qt.Checked:
                checked_items.append(str(candidate.data(QtCore.Qt.UserRole)))
        if len(checked_items) > self.group.choose:
            # Revert the last change
            with QtCore.QSignalBlocker(self.list_widget):
                item.setCheckState(QtCore.Qt.Unchecked)
            return
        self.selectionChanged.emit(self.group.id, checked_items)


class SpellItemWidget(QtWidgets.QWidget):
    knownToggled = QtCore.Signal(str, bool)
    preparedToggled = QtCore.Signal(str, bool)

    def __init__(self, spell: dict, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.spell = spell
        self.spell_index = spell["index"].lower()

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        self.name_label = QtWidgets.QLabel(spell.get("name", "Unknown Spell"))
        font = self.name_label.font()
        font.setBold(True)
        self.name_label.setFont(font)

        info_label = QtWidgets.QLabel(
            f"{spell.get('school', {}).get('name', '')} · {spell.get('casting_time', '')}"
        )
        info_label.setStyleSheet("color: #666;")

        self.known_box = QtWidgets.QCheckBox("Known")
        self.prepared_box = QtWidgets.QCheckBox("Prepared")

        self.known_box.stateChanged.connect(self._on_known_changed)
        self.prepared_box.stateChanged.connect(self._on_prepared_changed)

        layout.addWidget(self.name_label, stretch=2)
        layout.addWidget(info_label, stretch=2)
        layout.addWidget(self.known_box)
        layout.addWidget(self.prepared_box)
        layout.addStretch(1)

        tooltip = "\n".join(spell.get("desc", []))
        if spell.get("higher_level"):
            tooltip += "\n\n" + "\n".join(spell.get("higher_level"))
        self.setToolTip(tooltip)

    def update_state(self, known: bool, prepared: bool) -> None:
        with QtCore.QSignalBlocker(self.known_box):
            self.known_box.setChecked(known)
        with QtCore.QSignalBlocker(self.prepared_box):
            self.prepared_box.setChecked(prepared)
        self.prepared_box.setEnabled(known)

    # ------------------------------------------------------------------
    def _on_known_changed(self, state: int) -> None:
        is_checked = state == QtCore.Qt.Checked
        if not is_checked:
            with QtCore.QSignalBlocker(self.prepared_box):
                self.prepared_box.setChecked(False)
        self.prepared_box.setEnabled(is_checked)
        self.knownToggled.emit(self.spell_index, is_checked)

    def _on_prepared_changed(self, state: int) -> None:
        is_checked = state == QtCore.Qt.Checked
        if is_checked and not self.known_box.isChecked():
            with QtCore.QSignalBlocker(self.known_box):
                self.known_box.setChecked(True)
            self.prepared_box.setEnabled(True)
            self.knownToggled.emit(self.spell_index, True)
        self.preparedToggled.emit(self.spell_index, is_checked)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, srd: Optional[SRDData] = None, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.viewmodel = CharacterViewModel(srd)
        self.setWindowTitle("D&D 5e Character Builder")
        self.resize(1280, 860)

        self._ability_widgets: Dict[str, Dict[str, QtWidgets.QWidget]] = {}
        self._skill_rows: Dict[str, int] = {}
        self._skill_proficiency_boxes: Dict[str, QtWidgets.QCheckBox] = {}
        self._skill_expertise_boxes: Dict[str, QtWidgets.QCheckBox] = {}
        self._skill_source_labels: Dict[str, QtWidgets.QLabel] = {}
        self._skill_bonus_labels: Dict[str, QtWidgets.QLabel] = {}
        self._spell_lists: Dict[int, QtWidgets.QListWidget] = {}
        self._spell_widgets: Dict[str, SpellItemWidget] = {}
        self._choice_widgets: Dict[str, ChoiceGroupWidget] = {}
        self._is_refreshing = False

        self._build_ui()
        self._connect_signals()
        self._apply_theme()
        self.refresh_all()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        container = QtWidgets.QWidget(self)
        layout = QtWidgets.QVBoxLayout(container)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        header = QtWidgets.QFrame()
        header.setObjectName("headerFrame")
        header_layout = QtWidgets.QHBoxLayout(header)
        header_layout.setContentsMargins(18, 12, 18, 12)
        header_layout.setSpacing(12)

        self.title_label = QtWidgets.QLabel("D&D 5e Character Builder")
        title_font = QtGui.QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        self.title_label.setFont(title_font)

        self.subtitle_label = QtWidgets.QLabel("Craft rich NPCs in seconds")
        subtitle_font = QtGui.QFont()
        subtitle_font.setPointSize(11)
        self.subtitle_label.setFont(subtitle_font)
        self.subtitle_label.setObjectName("subtitleLabel")

        header_layout.addWidget(self.title_label)
        header_layout.addStretch(1)
        header_layout.addWidget(self.subtitle_label)

        layout.addWidget(header)

        self.tabs = QtWidgets.QTabWidget(container)
        self.tabs.setTabPosition(QtWidgets.QTabWidget.North)
        self.tabs.setDocumentMode(True)
        self.tabs.setMovable(False)
        layout.addWidget(self.tabs)
        self.setCentralWidget(container)

        self.tabs.addTab(self._build_basics_tab(), "Basics")
        self.tabs.addTab(self._build_abilities_tab(), "Abilities")
        self.tabs.addTab(self._build_skills_tab(), "Skills")
        self.tabs.addTab(self._build_spells_tab(), "Spells")
        self.tabs.addTab(self._build_summary_tab(), "Summary")

    # ------------------------------------------------------------------
    def _build_basics_tab(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(widget)
        form.setLabelAlignment(QtCore.Qt.AlignRight)

        buttons_layout = QtWidgets.QHBoxLayout()
        self.randomize_button = QtWidgets.QPushButton(" Random Character")
        self.randomize_button.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_BrowserReload))
        self.clear_button = QtWidgets.QPushButton(" Clear")
        self.clear_button.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_DialogResetButton))
        buttons_layout.addWidget(self.randomize_button)
        buttons_layout.addWidget(self.clear_button)
        buttons_layout.addStretch(1)
        buttons_widget = QtWidgets.QWidget()
        buttons_widget.setLayout(buttons_layout)
        form.addRow(buttons_widget)

        self.name_edit = QtWidgets.QLineEdit()
        form.addRow("Name", self.name_edit)

        self.level_spin = QtWidgets.QSpinBox()
        self.level_spin.setRange(1, 20)
        self.level_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.level_slider.setRange(1, 20)
        level_layout = QtWidgets.QHBoxLayout()
        level_layout.addWidget(self.level_spin)
        level_layout.addWidget(self.level_slider)
        level_widget = QtWidgets.QWidget()
        level_widget.setLayout(level_layout)
        form.addRow("Level", level_widget)

        self.race_combo = self._create_combo()
        form.addRow("Race", self.race_combo)

        self.subrace_combo = self._create_combo()
        form.addRow("Subrace", self.subrace_combo)

        self.class_combo = self._create_combo()
        form.addRow("Class", self.class_combo)

        self.subclass_combo = self._create_combo()
        form.addRow("Subclass", self.subclass_combo)

        self.background_combo = self._create_combo()
        form.addRow("Background", self.background_combo)

        self.alignment_combo = self._create_combo()
        form.addRow("Alignment", self.alignment_combo)

        self.gender_combo = self._create_combo()
        form.addRow("Gender", self.gender_combo)

        self.notes_edit = QtWidgets.QTextEdit()
        self.notes_edit.setPlaceholderText("Personality traits, ideals, bonds, appearance, etc.")
        form.addRow("Notes", self.notes_edit)

        return widget

    def _build_abilities_tab(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        table = QtWidgets.QTableWidget(len(ABILITY_SCORES), 7, widget)
        table.setHorizontalHeaderLabels([
            "Ability",
            "Base",
            "Racial",
            "Subrace",
            "Bonus",
            "Total",
            "Modifier",
        ])
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        layout.addWidget(table)
        self.ability_table = table

        for row, ability in enumerate(ABILITY_SCORES):
            pretty = ABILITY_NAMES[ability]
            table.setItem(row, 0, self._make_readonly_item(pretty))

            base_spin = QtWidgets.QSpinBox()
            base_spin.setRange(1, 30)
            base_spin.valueChanged.connect(lambda value, ab=ability: self.viewmodel.set_base_ability_score(ab, value))
            table.setCellWidget(row, 1, base_spin)

            racial_label = QtWidgets.QLabel("0")
            racial_label.setAlignment(QtCore.Qt.AlignCenter)
            table.setCellWidget(row, 2, racial_label)

            subrace_label = QtWidgets.QLabel("0")
            subrace_label.setAlignment(QtCore.Qt.AlignCenter)
            table.setCellWidget(row, 3, subrace_label)

            manual_spin = QtWidgets.QSpinBox()
            manual_spin.setRange(-5, 10)
            manual_spin.valueChanged.connect(lambda value, ab=ability: self.viewmodel.set_manual_ability_bonus(ab, value))
            table.setCellWidget(row, 4, manual_spin)

            total_label = QtWidgets.QLabel("10")
            total_label.setAlignment(QtCore.Qt.AlignCenter)
            table.setCellWidget(row, 5, total_label)

            mod_label = QtWidgets.QLabel("+0")
            mod_label.setAlignment(QtCore.Qt.AlignCenter)
            table.setCellWidget(row, 6, mod_label)

            self._ability_widgets[ability] = {
                "base": base_spin,
                "racial": racial_label,
                "subrace": subrace_label,
                "manual": manual_spin,
                "total": total_label,
                "modifier": mod_label,
            }

        return widget

    def _build_skills_tab(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        layout.addWidget(splitter)

        skills_widget = QtWidgets.QWidget()
        skills_layout = QtWidgets.QVBoxLayout(skills_widget)
        skill_table = QtWidgets.QTableWidget(len(SKILL_NAMES), 6)
        skill_table.setHorizontalHeaderLabels([
            "Skill",
            "Ability",
            "Source",
            "Proficient",
            "Expertise",
            "Bonus",
        ])
        skill_table.verticalHeader().setVisible(False)
        skill_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        skill_table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        skill_table.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
        skill_table.horizontalHeader().setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeToContents)
        skill_table.horizontalHeader().setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeToContents)
        skills_layout.addWidget(skill_table)
        self.skill_table = skill_table

        for row, (skill_idx, skill_name) in enumerate(sorted(SKILL_NAMES.items(), key=lambda item: item[1])):
            ability = SKILL_TO_ABILITY[skill_idx]
            self._skill_rows[skill_idx] = row
            skill_table.setItem(row, 0, self._make_readonly_item(skill_name))
            skill_table.setItem(row, 1, self._make_readonly_item(ability.upper()))

            source_label = QtWidgets.QLabel("-")
            source_label.setAlignment(QtCore.Qt.AlignCenter)
            skill_table.setCellWidget(row, 2, source_label)
            self._skill_source_labels[skill_idx] = source_label

            prof_box = QtWidgets.QCheckBox()
            prof_box.stateChanged.connect(lambda state, idx=skill_idx: self.viewmodel.toggle_skill_proficiency(idx, state == QtCore.Qt.Checked))
            skill_table.setCellWidget(row, 3, prof_box)
            self._skill_proficiency_boxes[skill_idx] = prof_box

            expertise_box = QtWidgets.QCheckBox()
            expertise_box.stateChanged.connect(lambda state, idx=skill_idx: self.viewmodel.toggle_expertise(idx, state == QtCore.Qt.Checked))
            skill_table.setCellWidget(row, 4, expertise_box)
            self._skill_expertise_boxes[skill_idx] = expertise_box

            bonus_label = QtWidgets.QLabel("+0")
            bonus_label.setAlignment(QtCore.Qt.AlignCenter)
            skill_table.setCellWidget(row, 5, bonus_label)
            self._skill_bonus_labels[skill_idx] = bonus_label

        splitter.addWidget(skills_widget)

        choices_widget = QtWidgets.QWidget()
        choices_layout = QtWidgets.QVBoxLayout(choices_widget)
        choices_layout.setContentsMargins(0, 0, 0, 0)
        self.choice_scroll = QtWidgets.QScrollArea()
        self.choice_scroll.setWidgetResizable(True)
        self.choice_inner = QtWidgets.QWidget()
        self.choice_layout = QtWidgets.QVBoxLayout(self.choice_inner)
        self.choice_scroll.setWidget(self.choice_inner)
        choices_layout.addWidget(QtWidgets.QLabel("Choice-Based Proficiencies"))
        choices_layout.addWidget(self.choice_scroll)

        splitter.addWidget(choices_widget)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)

        return widget

    def _build_spells_tab(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        self.spell_tabs = QtWidgets.QTabWidget()
        layout.addWidget(self.spell_tabs)
        return widget

    def _build_summary_tab(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        self.summary_browser = QtWidgets.QTextBrowser()
        self.summary_browser.setOpenExternalLinks(False)
        layout.addWidget(self.summary_browser)

        export_layout = QtWidgets.QHBoxLayout()
        self.quit_button = QtWidgets.QPushButton(" Quit")
        self.quit_button.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_DialogCloseButton))
        export_layout.addWidget(self.quit_button)
        export_layout.addStretch(1)
        self.copy_button = QtWidgets.QPushButton(" Copy NPC Statblock")
        self.copy_button.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_FileDialogDetailedView))
        self.export_button = QtWidgets.QPushButton(" Export NPC Statblock…")
        self.export_button.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_ComputerIcon))
        export_layout.addWidget(self.copy_button)
        export_layout.addWidget(self.export_button)
        layout.addLayout(export_layout)
        return widget

    # ------------------------------------------------------------------
    def _connect_signals(self) -> None:
        self.name_edit.textChanged.connect(self.viewmodel.set_name)
        self.level_spin.valueChanged.connect(self._on_level_spin_changed)
        self.level_slider.valueChanged.connect(self._on_level_slider_changed)
        self.race_combo.currentIndexChanged.connect(lambda _: self._on_combo_changed(self.race_combo, self.viewmodel.set_race))
        self.subrace_combo.currentIndexChanged.connect(lambda _: self._on_combo_changed(self.subrace_combo, self.viewmodel.set_subrace))
        self.class_combo.currentIndexChanged.connect(lambda _: self._on_combo_changed(self.class_combo, self.viewmodel.set_class))
        self.subclass_combo.currentIndexChanged.connect(lambda _: self._on_combo_changed(self.subclass_combo, self.viewmodel.set_subclass))
        self.background_combo.currentIndexChanged.connect(lambda _: self._on_combo_changed(self.background_combo, self.viewmodel.set_background))
        self.alignment_combo.currentIndexChanged.connect(lambda _: self._on_combo_changed(self.alignment_combo, self.viewmodel.set_alignment))
        self.notes_edit.textChanged.connect(self._on_notes_changed)
        self.copy_button.clicked.connect(self._copy_statblock)
        self.export_button.clicked.connect(self._export_statblock)
        self.quit_button.clicked.connect(self._on_quit_clicked)
        self.randomize_button.clicked.connect(self._on_randomize_clicked)
        self.clear_button.clicked.connect(self._on_clear_clicked)
        self.gender_combo.currentIndexChanged.connect(lambda _: self._on_combo_changed(self.gender_combo, self.viewmodel.set_gender))

        self.viewmodel.stateChanged.connect(self.refresh_all)
        self.viewmodel.derivedChanged.connect(self._refresh_summary)
        self.viewmodel.choiceGroupsChanged.connect(self._rebuild_choice_widgets)

    # ------------------------------------------------------------------
    def refresh_all(self) -> None:
        if self._is_refreshing:
            return
        self._is_refreshing = True
        try:
            self._populate_basics()
            self._refresh_abilities()
            self._refresh_skill_table()
            self._rebuild_choice_widgets()
            self._refresh_spells()
            self._refresh_summary()
        finally:
            self._is_refreshing = False

    def _populate_basics(self) -> None:
        state = self.viewmodel.state
        self._block(self.name_edit, lambda: self.name_edit.setText(state.name))
        self._block(self.level_spin, lambda: self.level_spin.setValue(state.level))
        self._block(self.level_slider, lambda: self.level_slider.setValue(state.level))

        self._populate_combo(self.race_combo, self.viewmodel.race_options())
        self._set_combo_to_value(self.race_combo, state.race)
        self._populate_combo(self.subrace_combo, self.viewmodel.subrace_options())
        self._set_combo_to_value(self.subrace_combo, state.subrace)
        self._populate_combo(self.class_combo, self.viewmodel.class_options())
        self._set_combo_to_value(self.class_combo, state.character_class)
        self._populate_combo(self.subclass_combo, self.viewmodel.subclass_options())
        self._set_combo_to_value(self.subclass_combo, state.subclass)
        self._populate_combo(self.background_combo, self.viewmodel.background_options())
        self._set_combo_to_value(self.background_combo, state.background)

        alignments = [(entry["index"], entry["name"]) for entry in self.viewmodel.srd.alignments]
        self._populate_combo(self.alignment_combo, alignments)
        self._set_combo_to_value(self.alignment_combo, state.alignment)

        gender_options = [("male", "Male"), ("female", "Female")]
        self._populate_combo(self.gender_combo, gender_options)
        self._set_combo_to_value(self.gender_combo, state.gender)

        self._block(self.notes_edit, lambda: self.notes_edit.setPlainText(state.notes))

    def _refresh_abilities(self) -> None:
        breakdown = self.viewmodel.ability_score_breakdown()
        for ability, widgets in self._ability_widgets.items():
            data = breakdown[ability]
            self._block(widgets["base"], lambda value=data["base"]: widgets["base"].setValue(value))
            self._block(widgets["manual"], lambda value=data["manual"]: widgets["manual"].setValue(value))
            widgets["racial"].setText(str(data["racial"]))
            widgets["subrace"].setText(str(data["subrace"]))
            widgets["total"].setText(str(data["total"]))
            modifier = data["total"]
            mod_value = (modifier - 10) // 2
            widgets["modifier"].setText(f"{mod_value:+d}")

    def _refresh_skill_table(self) -> None:
        state = self.viewmodel.state
        auto_skills = state.automatic_skill_proficiencies
        choice_skills = self.viewmodel.choice_skill_selections()
        combined = auto_skills | choice_skills | state.selected_skill_proficiencies
        for skill, row in self._skill_rows.items():
            source_fragments: List[str] = []
            if skill in auto_skills:
                source_fragments.append("auto")
            if skill in choice_skills:
                source_fragments.append("choice")
            if skill in state.selected_skill_proficiencies:
                source_fragments.append("manual")
            self._skill_source_labels[skill].setText(", ".join(source_fragments) or "-")

            prof_box = self._skill_proficiency_boxes[skill]
            with QtCore.QSignalBlocker(prof_box):
                prof_box.setChecked(skill in combined)
            prof_box.setEnabled(skill not in auto_skills and skill not in choice_skills)

            expertise_box = self._skill_expertise_boxes[skill]
            with QtCore.QSignalBlocker(expertise_box):
                expertise_box.setChecked(skill in state.selected_skill_expertise)
            expertise_box.setEnabled(skill in combined)

            bonus = state.derived.skill_bonuses.get(skill, 0)
            self._skill_bonus_labels[skill].setText(f"{bonus:+d}")

    def _rebuild_choice_widgets(self) -> None:
        # Clear existing widgets
        for widget in self._choice_widgets.values():
            widget.setParent(None)
            widget.deleteLater()
        self._choice_widgets.clear()

        # Remove all items from layout
        while self.choice_layout.count():
            item = self.choice_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        groups = self.viewmodel.choice_groups_for_display()
        if not groups:
            placeholder = QtWidgets.QLabel("No choices required for current selections.")
            placeholder.setAlignment(QtCore.Qt.AlignCenter)
            self.choice_layout.addWidget(placeholder)
        else:
            for group in groups:
                widget = ChoiceGroupWidget(group)
                widget.selectionChanged.connect(self._on_choice_group_changed)
                widget.set_selected(self.viewmodel.state.choice_selections.get(group.id, set()))
                self.choice_layout.addWidget(widget)
                self._choice_widgets[group.id] = widget
        self.choice_layout.addStretch(1)

    def _refresh_spells(self) -> None:
        spell_data = self.viewmodel.spells_by_level()
        # Rebuild tabs if counts changed
        existing_levels = set(self._spell_lists.keys())
        desired_levels = set(spell_data.keys())
        if existing_levels != desired_levels:
            self.spell_tabs.clear()
            self._spell_lists.clear()
            self._spell_widgets.clear()
            for level in sorted(spell_data.keys()):
                list_widget = QtWidgets.QListWidget()
                list_widget.setSpacing(4)
                self._spell_lists[level] = list_widget
                level_label = "Cantrips" if level == 0 else f"Level {level}"
                self.spell_tabs.addTab(list_widget, level_label)

        self._spell_widgets.clear()
        for level, list_widget in self._spell_lists.items():
            list_widget.clear()
            for spell in spell_data.get(level, []):
                item = QtWidgets.QListWidgetItem(list_widget)
                widget = SpellItemWidget(spell)
                widget.knownToggled.connect(lambda checked, idx=spell["index"].lower(): self.viewmodel.toggle_spell(idx, "known", checked))
                widget.preparedToggled.connect(lambda checked, idx=spell["index"].lower(): self.viewmodel.toggle_spell(idx, "prepared", checked))
                list_widget.addItem(item)
                list_widget.setItemWidget(item, widget)
                item.setSizeHint(widget.sizeHint())
                self._spell_widgets[spell["index"].lower()] = widget

        self._refresh_spell_states()

    def _refresh_spell_states(self) -> None:
        selected_known = self.viewmodel.state.selected_spells.get("known", set())
        selected_prepared = self.viewmodel.state.selected_spells.get("prepared", set())
        for index, widget in self._spell_widgets.items():
            widget.update_state(index in selected_known, index in selected_prepared)

    def _refresh_summary(self) -> None:
        state = self.viewmodel.state
        class_data = self.viewmodel.srd.classes.get(state.character_class) if state.character_class else None
        race_data = self.viewmodel.srd.races.get(state.race) if state.race else None

        ability_lines = []
        for ability in ABILITY_SCORES:
            total = state.total_ability_score(ability)
            mod = (total - 10) // 2
            ability_lines.append(f"<b>{ABILITY_NAMES[ability]}:</b> {total} ({mod:+d})")

        saving_lines = []
        for ability, bonus in state.derived.saving_throws.items():
            saving_lines.append(f"{ABILITY_NAMES[ability]} {bonus:+d}")

        skill_lines = []
        for skill_idx, name in sorted(SKILL_NAMES.items(), key=lambda item: item[1]):
            bonus = state.derived.skill_bonuses.get(skill_idx, 0)
            skill_lines.append(f"{name}: {bonus:+d}")

        spell_slots = state.derived.spell_slots

        def _ordinal_suffix(num: int) -> str:
            if 10 <= num % 100 <= 20:
                return "th"
            return {1: "st", 2: "nd", 3: "rd"}.get(num % 10, "th")

        slot_line = ", ".join(
            f"{lvl}{_ordinal_suffix(lvl)}: {count}" for lvl, count in spell_slots.items()
        ) if spell_slots else "None"

        features = self._collect_features()
        feature_html = "".join(f"<li><b>{name}</b>: {desc}</li>" for name, desc in features)

        languages = sorted(self.viewmodel.selected_languages())
        languages_html = ", ".join(languages) if languages else "Common"

        currency = state.currency or {}
        currency_line = ", ".join(
            f"{amount} {denom.upper()}" for denom, amount in currency.items() if amount
        )
        if not currency_line:
            currency_line = "None"

        equipment_lines: List[str] = []
        if state.equipment:
            from collections import Counter

            counts = Counter(state.equipment)
            for idx, qty in counts.items():
                base_index, bonus = _split_magic_index(idx)
                item = self.viewmodel.srd.equipment.get(base_index)
                name = item.get("name") if item else base_index.replace("-", " ").title()
                if bonus:
                    name = f"{name} +{bonus}"
                if qty > 1:
                    equipment_lines.append(f"{qty} × {name}")
                else:
                    equipment_lines.append(name)
        equipment_html = ", ".join(equipment_lines) if equipment_lines else "—"

        biography_html = state.biography.replace("\n", "<br/>") if state.biography else ""

        summary_html = f"""
        <h2>{state.name}</h2>
        <p>
            Level {state.level} {class_data.name if class_data else ''}{' / ' if class_data and race_data else ''}{race_data.name if race_data else ''}<br/>
            Alignment: {state.alignment or 'Unaligned'}<br/>
            Gender: {state.gender.title() if state.gender else '—'}
        </p>
        <h3>Derived Stats</h3>
        <ul>
            <li>Proficiency Bonus: {state.derived.proficiency_bonus:+d}</li>
            <li>Hit Points: {state.derived.max_hit_points} ({state.derived.hit_die or 'n/a'})</li>
            <li>Armor Class: {state.derived.armor_class}</li>
            <li>Initiative: {state.derived.initiative:+d}</li>
            <li>Speed: {state.derived.speed} ft.</li>
            <li>Passive Perception: {state.derived.passive_perception}</li>
            <li>Spell Save DC / Attack: {state.derived.spell_dc or '—'} / {state.derived.spell_attack or '—'}</li>
            <li>Spell Slots: {slot_line}</li>
        </ul>
        <h3>Ability Scores</h3>
        <p>{'<br/>'.join(ability_lines)}</p>
        <h3>Saving Throws</h3>
        <p>{', '.join(saving_lines)}</p>
        <h3>Skills</h3>
        <p>{', '.join(skill_lines)}</p>
        <h3>Languages</h3>
        <p>{languages_html}</p>
        <h3>Currency</h3>
        <p>{currency_line}</p>
        <h3>Equipment</h3>
        <p>{equipment_html}</p>
        <h3>Features</h3>
        <ul>{feature_html}</ul>
        {f'<h3>Biography</h3><p>{biography_html}</p>' if biography_html else ''}
        """
        self.summary_browser.setHtml(summary_html)

    def _collect_features(self) -> List[tuple]:
        state = self.viewmodel.state
        features: List[tuple] = []
        race = self.viewmodel.srd.races.get(state.race) if state.race else None
        if race:
            for trait in race.traits:
                features.append((trait.get("name", "Trait"), " ".join(trait.get("desc", []))))
            if state.subrace and state.subrace in race.subraces:
                subrace = race.subraces[state.subrace]
                for trait in subrace.traits:
                    features.append((trait.get("name", "Trait"), " ".join(trait.get("desc", []))))

        class_data = self.viewmodel.srd.classes.get(state.character_class) if state.character_class else None
        if class_data:
            for lvl in sorted(class_data.levels.keys()):
                if lvl > state.level:
                    continue
                for feature in class_data.levels[lvl].features:
                    features.append((feature.get("name", f"Feature {lvl}"), " ".join(feature.get("desc", []))))
            if state.subclass and state.subclass in class_data.subclasses:
                subclass = class_data.subclasses[state.subclass]
                for lvl, feats in subclass.features_by_level.items():
                    if lvl > state.level:
                        continue
                    for feat in feats:
                        features.append((feat.get("name", f"Subclass Feature {lvl}"), " ".join(feat.get("desc", []))))

        background = self.viewmodel.srd.backgrounds.get(state.background) if state.background else None
        if background and background.feature:
            feature = background.feature
            features.append((feature.get("name", "Background Feature"), " ".join(feature.get("desc", []))))
        return features

    # ------------------------------------------------------------------
    def _export_statblock(self) -> None:
        from ..export.statblock import export_character_to_statblock

        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export NPC Statblock",
            "character-statblock.txt",
            "Text Files (*.txt)"
        )
        if not path:
            return
        try:
            export_character_to_statblock(self.viewmodel, Path(path))
        except Exception as exc:  # pragma: no cover - surfacing to UI
            QtWidgets.QMessageBox.critical(self, "Export Failed", str(exc))
        else:
            QtWidgets.QMessageBox.information(self, "Export Complete", f"Saved to {path}")

    def _copy_statblock(self) -> None:
        from ..export.statblock import build_statblock_text

        statblock = build_statblock_text(self.viewmodel)
        QtWidgets.QApplication.clipboard().setText(statblock)
        self.statusBar().showMessage("NPC statblock copied to clipboard.", 5000)

    # ------------------------------------------------------------------
    def _on_quit_clicked(self) -> None:
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.quit()

    # ------------------------------------------------------------------
    def _apply_theme(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background-color: #1c1f26;
            }
            QWidget {
                color: #e0e3eb;
                font-size: 11pt;
            }
            QFrame#headerFrame {
                background-color: #242a35;
                border-radius: 12px;
                border: 1px solid #2f3642;
            }
            QTabWidget::pane {
                border: 1px solid #2f3642;
                border-radius: 12px;
                background-color: #2a313d;
            }
            QTabBar::tab {
                background: #252b36;
                padding: 8px 20px;
                margin: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            QTabBar::tab:selected {
                background: #3a4354;
                color: #f5f7ff;
            }
            QPushButton {
                background-color: #374050;
                border: 1px solid #455065;
                border-radius: 6px;
                padding: 8px 14px;
            }
            QPushButton:hover {
                background-color: #485369;
            }
            QPushButton:pressed {
                background-color: #2f3642;
            }
            QComboBox, QSpinBox, QLineEdit, QTextEdit {
                background-color: #2f3642;
                border: 1px solid #3b4454;
                border-radius: 6px;
                padding: 4px 8px;
                selection-background-color: #4c5a73;
            }
            QTextBrowser {
                background-color: #232831;
                border: 1px solid #323a48;
                border-radius: 12px;
                padding: 12px;
            }
            QListWidget {
                background-color: #2b313d;
                border: 1px solid #3b4454;
                border-radius: 6px;
            }
            QGroupBox {
                border: 1px solid #343c4a;
                border-radius: 10px;
                margin-top: 14px;
                padding: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 6px;
                color: #f0f4ff;
            }
            QStatusBar {
                background-color: #242a34;
                color: #cfd4e4;
            }
            QLabel#subtitleLabel {
                color: #9aa3bb;
            }
            """
        )
        self.statusBar().showMessage("Ready", 2000)

    # ------------------------------------------------------------------
    def _on_level_spin_changed(self, value: int) -> None:
        self.level_slider.setValue(value)
        self.viewmodel.set_level(value)

    def _on_level_slider_changed(self, value: int) -> None:
        self.level_spin.setValue(value)
        self.viewmodel.set_level(value)

    def _on_combo_changed(self, combo: QtWidgets.QComboBox, setter) -> None:
        value = combo.currentData()
        setter(value)

    def _on_choice_group_changed(self, group_id: str, selections: List[str]) -> None:
        self.viewmodel.set_choice_selection(group_id, selections)

    def _on_notes_changed(self) -> None:
        text = self.notes_edit.toPlainText()
        self.viewmodel.state.notes = text
        self.viewmodel._lock_field("notes", bool(text.strip()))
        self.viewmodel.stateChanged.emit()

    def _on_randomize_clicked(self) -> None:
        self.viewmodel.randomize_character()

    def _on_clear_clicked(self) -> None:
        self.viewmodel.state.reset()
        self.viewmodel._refresh_everything()

    def _populate_combo(self, combo: QtWidgets.QComboBox, options: Iterable[tuple]) -> None:
        with QtCore.QSignalBlocker(combo):
            combo.clear()
            combo.addItem("—", None)
            for value, label in options:
                combo.addItem(label, value)

    def _set_combo_to_value(self, combo: QtWidgets.QComboBox, value: Optional[str]) -> None:
        with QtCore.QSignalBlocker(combo):
            index = combo.findData(value)
            combo.setCurrentIndex(index if index >= 0 else 0)

    def _block(self, widget: QtCore.QObject, setter) -> None:
        with QtCore.QSignalBlocker(widget):
            setter()

    def _create_combo(self) -> QtWidgets.QComboBox:
        combo = QtWidgets.QComboBox()
        combo.setEditable(False)
        return combo

    def _make_readonly_item(self, text: str) -> QtWidgets.QTableWidgetItem:
        item = QtWidgets.QTableWidgetItem(text)
        item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
        return item


def _split_magic_index(index: str) -> Tuple[str, int]:
    if "+" in index:
        base, bonus = index.split("+", 1)
        try:
            return base, int(bonus)
        except ValueError:
            return base, 0
    return index, 0


def launch_app() -> None:
    import sys

    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
