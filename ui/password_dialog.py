"""
Password authentication dialog for the Database Synchronization Application.

This module provides dialogs for password authentication and password setup
with proper validation and security considerations.
"""

from typing import Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QMessageBox,
    QProgressBar, QCheckBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QPixmap

from utils.constants import VALIDATION_RULES, ERROR_MESSAGES


class PasswordDialog(QDialog):
    """Dialog for password authentication and setup."""

    def __init__(self, parent=None, is_first_run: bool = False, is_change_password: bool = False):
        """
        Initialize the password dialog.

        Args:
            parent: Parent widget
            is_first_run: True if this is first run setup
            is_change_password: True if changing existing password
        """
        super().__init__(parent)
        self.is_first_run = is_first_run
        self.is_change_password = is_change_password
        self.password_strength = 0

        self.setup_ui()
        self.setup_connections()

    def setup_ui(self):
        """Set up the user interface."""
        if self.is_first_run:
            self.setWindowTitle("First Run - Set Password")
            title_text = "Welcome! Set a password to secure your settings."
        elif self.is_change_password:
            self.setWindowTitle("Change Password")
            title_text = "Change your settings password."
        else:
            self.setWindowTitle("Authentication Required")
            title_text = "Enter your password to access settings."

        self.setModal(True)
        self.setFixedSize(400, 300)

        # Main layout
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 20, 30, 20)

        # Title
        title_label = QLabel(title_text)
        title_label.setStyleSheet("font-weight: bold; font-size: 14px; margin-bottom: 10px;")
        title_label.setWordWrap(True)
        layout.addWidget(title_label)

        # Form layout
        form_layout = QFormLayout()
        form_layout.setSpacing(15)

        if self.is_change_password:
            # Current password field
            self.current_password = QLineEdit()
            self.current_password.setEchoMode(QLineEdit.Password)
            self.current_password.setPlaceholderText("Enter current password")
            form_layout.addRow("Current Password:", self.current_password)

        if self.is_first_run or self.is_change_password:
            # New password field
            self.new_password = QLineEdit()
            self.new_password.setEchoMode(QLineEdit.Password)
            self.new_password.setPlaceholderText("Enter new password")
            form_layout.addRow("New Password:", self.new_password)

            # Password strength indicator
            self.strength_bar = QProgressBar()
            self.strength_bar.setMaximum(100)
            self.strength_bar.setValue(0)
            self.strength_bar.setTextVisible(False)
            self.strength_bar.setMaximumHeight(6)
            form_layout.addRow("Strength:", self.strength_bar)

            self.strength_label = QLabel("Enter a password")
            self.strength_label.setStyleSheet("font-size: 11px; color: gray;")
            form_layout.addRow("", self.strength_label)

            # Confirm password field
            self.confirm_password = QLineEdit()
            self.confirm_password.setEchoMode(QLineEdit.Password)
            self.confirm_password.setPlaceholderText("Confirm new password")
            form_layout.addRow("Confirm Password:", self.confirm_password)

            # Show password checkbox
            self.show_password_cb = QCheckBox("Show passwords")
            form_layout.addRow("", self.show_password_cb)

        else:
            # Login password field
            self.password = QLineEdit()
            self.password.setEchoMode(QLineEdit.Password)
            self.password.setPlaceholderText("Enter password")
            form_layout.addRow("Password:", self.password)

            # Show password checkbox
            self.show_password_cb = QCheckBox("Show password")
            form_layout.addRow("", self.show_password_cb)

        layout.addLayout(form_layout)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.cancel_button = QPushButton("Cancel")
        self.ok_button = QPushButton("OK")

        if self.is_first_run:
            self.ok_button.setText("Set Password")
        elif self.is_change_password:
            self.ok_button.setText("Change Password")
        else:
            self.ok_button.setText("Login")

        self.ok_button.setDefault(True)

        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.ok_button)

        layout.addLayout(button_layout)

        # Set focus to appropriate field
        if hasattr(self, 'current_password'):
            self.current_password.setFocus()
        elif hasattr(self, 'new_password'):
            self.new_password.setFocus()
        else:
            self.password.setFocus()

    def setup_connections(self):
        """Set up signal connections."""
        self.ok_button.clicked.connect(self.validate_and_accept)
        self.cancel_button.clicked.connect(self.reject)

        # Show/hide password functionality
        self.show_password_cb.toggled.connect(self.toggle_password_visibility)

        if self.is_first_run or self.is_change_password:
            # Password strength checking
            self.new_password.textChanged.connect(self.check_password_strength)
            self.confirm_password.textChanged.connect(self.validate_password_match)

            # Enable OK button only when passwords are valid
            self.new_password.textChanged.connect(self.update_ok_button_state)
            self.confirm_password.textChanged.connect(self.update_ok_button_state)

            if hasattr(self, 'current_password'):
                self.current_password.textChanged.connect(self.update_ok_button_state)

        # Enter key handling
        if hasattr(self, 'password'):
            self.password.returnPressed.connect(self.validate_and_accept)
        if hasattr(self, 'confirm_password'):
            self.confirm_password.returnPressed.connect(self.validate_and_accept)

    def toggle_password_visibility(self, visible: bool):
        """Toggle password field visibility."""
        echo_mode = QLineEdit.Normal if visible else QLineEdit.Password

        if hasattr(self, 'password'):
            self.password.setEchoMode(echo_mode)
        if hasattr(self, 'current_password'):
            self.current_password.setEchoMode(echo_mode)
        if hasattr(self, 'new_password'):
            self.new_password.setEchoMode(echo_mode)
        if hasattr(self, 'confirm_password'):
            self.confirm_password.setEchoMode(echo_mode)

    def check_password_strength(self, password: str):
        """
        Check and display password strength.

        Args:
            password: Password to check
        """
        if not password:
            self.password_strength = 0
            self.strength_bar.setValue(0)
            self.strength_label.setText("Enter a password")
            self.strength_label.setStyleSheet("font-size: 11px; color: gray;")
            return

        score = 0
        feedback = []

        # Length check
        if len(password) >= VALIDATION_RULES['min_password_length']:
            score += 20
        else:
            feedback.append(f"At least {VALIDATION_RULES['min_password_length']} characters")

        if len(password) >= 8:
            score += 10

        # Character variety checks
        if any(c.islower() for c in password):
            score += 15
        else:
            feedback.append("lowercase letters")

        if any(c.isupper() for c in password):
            score += 15
        else:
            feedback.append("uppercase letters")

        if any(c.isdigit() for c in password):
            score += 20
        else:
            feedback.append("numbers")

        if any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            score += 20
        else:
            feedback.append("special characters")

        # Length bonus
        if len(password) >= 12:
            score += 10

        self.password_strength = min(100, score)
        self.strength_bar.setValue(self.password_strength)

        # Update strength label and color
        if self.password_strength < 30:
            strength_text = "Weak"
            color = "red"
        elif self.password_strength < 60:
            strength_text = "Fair"
            color = "orange"
        elif self.password_strength < 80:
            strength_text = "Good"
            color = "blue"
        else:
            strength_text = "Strong"
            color = "green"

        if feedback:
            suggestion = f"{strength_text} - Add: {', '.join(feedback[:2])}"
        else:
            suggestion = f"{strength_text} password"

        self.strength_label.setText(suggestion)
        self.strength_label.setStyleSheet(f"font-size: 11px; color: {color};")

        # Update progress bar color
        if self.password_strength < 30:
            bar_color = "#ff4444"
        elif self.password_strength < 60:
            bar_color = "#ff8800"
        elif self.password_strength < 80:
            bar_color = "#4488ff"
        else:
            bar_color = "#44aa44"

        self.strength_bar.setStyleSheet(f"""
            QProgressBar::chunk {{
                background-color: {bar_color};
            }}
        """)

    def validate_password_match(self):
        """Validate that passwords match."""
        if not hasattr(self, 'new_password') or not hasattr(self, 'confirm_password'):
            return

        if self.confirm_password.text() and self.new_password.text() != self.confirm_password.text():
            self.confirm_password.setStyleSheet("border: 1px solid red;")
        else:
            self.confirm_password.setStyleSheet("")

    def update_ok_button_state(self):
        """Update OK button enabled state based on input validation."""
        is_valid = True

        if self.is_first_run or self.is_change_password:
            # Check if passwords are filled and match
            if not self.new_password.text():
                is_valid = False
            elif len(self.new_password.text()) < VALIDATION_RULES['min_password_length']:
                is_valid = False
            elif self.new_password.text() != self.confirm_password.text():
                is_valid = False
            elif hasattr(self, 'current_password') and not self.current_password.text():
                is_valid = False
        else:
            # Check if password is filled
            if not self.password.text():
                is_valid = False

        self.ok_button.setEnabled(is_valid)

    def validate_and_accept(self):
        """Validate input and accept dialog if valid."""
        try:
            if self.is_first_run or self.is_change_password:
                # Validate new password
                new_password = self.new_password.text()
                confirm_password = self.confirm_password.text()

                if len(new_password) < VALIDATION_RULES['min_password_length']:
                    QMessageBox.warning(
                        self,
                        "Invalid Password",
                        f"Password must be at least {VALIDATION_RULES['min_password_length']} characters long."
                    )
                    return

                if len(new_password) > VALIDATION_RULES['max_password_length']:
                    QMessageBox.warning(
                        self,
                        "Invalid Password",
                        f"Password must be no more than {VALIDATION_RULES['max_password_length']} characters long."
                    )
                    return

                if new_password != confirm_password:
                    QMessageBox.warning(
                        self,
                        "Password Mismatch",
                        ERROR_MESSAGES['password_mismatch']
                    )
                    self.confirm_password.setFocus()
                    return

                # For password change, validate current password would be done by caller

            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred: {e}")

    def get_password(self) -> Optional[str]:
        """
        Get the password from the dialog.

        Returns:
            Password string, or None if invalid
        """
        if self.is_first_run or self.is_change_password:
            return self.new_password.text() if hasattr(self, 'new_password') else None
        else:
            return self.password.text() if hasattr(self, 'password') else None

    def get_current_password(self) -> Optional[str]:
        """
        Get the current password (for password change dialog).

        Returns:
            Current password string, or None if not applicable
        """
        if hasattr(self, 'current_password'):
            return self.current_password.text()
        return None

    def get_password_strength(self) -> int:
        """
        Get the password strength score.

        Returns:
            Password strength score (0-100)
        """
        return self.password_strength