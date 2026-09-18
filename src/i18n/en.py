#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
English language configuration file - contains translations and LLM prompts

Framework slim version: keeps only generic entries and entries required by
the account module. Extend here as needed for new projects.
"""

# ==================== UI Translations ====================
TRANSLATIONS = {
    # General / Brand
    'page_title': 'AI Teacher · Guided Learning',
    'brand_name': 'AI Teacher',
    'brand_slogan': 'Learning is easier together',
    'logo_alt': 'Site Icon',
    'back_to_home': '← Back to Home',

    # ==================== Account Module Translations ====================
    # Page titles
    'login_title': 'Login',
    'register_title': 'Register',

    # Form labels
    'login': 'Login',
    'register': 'Register',
    'logout': 'Logout',
    'username': 'Username',
    'email': 'Email/Phone',
    'password': 'Password',
    'confirm_password': 'Confirm Password',
    'username_or_email': 'Username or Email',

    # Placeholders
    'enter_username_or_email': 'Enter your username or email',
    'enter_password': 'Enter your password',
    'enter_email': 'Enter email or phone number',
    'choose_username': 'Choose a username',
    'create_password': 'Create a password',
    'confirm_password_placeholder': 'Confirm your password',

    # Options
    'remember_account': 'Remember account',
    'optional': 'optional',

    # Hints
    'no_account': "Don't have an account?",
    'has_account': 'Already have an account?',

    # Button states
    'logging_in': 'Logging in...',
    'registering': 'Registering...',
    'btn_cancel': 'Cancel',
    'btn_confirm': 'Confirm',

    # Error messages
    'error_account_required': 'Please enter username or email',
    'error_password_required': 'Please enter password',
    'error_email_required': 'Please enter email or phone number',
    'error_username_required': 'Please enter username',
    'error_invalid_email': 'Invalid email or phone format',
    'error_password_mismatch': 'Passwords do not match',
    'error_email_exists': 'This email or phone is already registered',
    'error_username_exists': 'This username is already taken',
    'error_account_not_found': 'Account not found',
    'error_wrong_password': 'Incorrect password',
    'error_login_failed': 'Login failed, please try again later',
    'error_register_failed': 'Registration failed, please try again later',
    'error_logout_failed': 'Logout failed',
    'error_network': 'Network error, please check your connection',
    'error_invalid_request': 'Invalid request',
    'error_user_not_found': 'User not found',
    'error_not_logged_in': 'Not logged in',
    'error_get_profile_failed': 'Failed to get user profile',

    # Success messages
    'success_login': 'Login successful',
    'success_register': 'Registration successful',
    'success_logout': 'Logged out',

    # Confirmation dialogs
    'confirm_logout': 'Are you sure you want to logout?',
    'confirm_logout_title': 'Confirm Logout',
    'confirm_logout_message': 'Are you sure you want to log out?',
    'btn_confirm_logout': 'Confirm Logout',

    # Error pages
    'error_page_not_found_title': 'Page Not Found',
    'error_page_not_found_message': 'The page does not exist, or the generation was interrupted.<br>Please check if the link is correct, or regenerate the page.',
}

# ==================== LLM Prompts (architecture example) ====================
LLM_PROMPTS = {
    'title_system': "You are a professional editor skilled at extracting precise and attractive titles for articles. Based on the article content provided by the user, generate a concise and clear title. Requirements: 1. Output only the title, no other explanations; 2. Keep title within 30 words; 3. Accurately summarize the core content of the article.",
    'title_user': "Please generate a title for the following article:\n\n{content}",
}
