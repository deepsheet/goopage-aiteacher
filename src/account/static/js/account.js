/**
 * 账户模块 JavaScript
 * 处理登录、注册等前端交互逻辑
 */

/**
 * 简单的翻译函数
 * @param {string} key - 翻译键
 * @return {string} - 翻译后的文本
 */
function getTranslation(key) {
    // 获取当前语言（从 HTML lang 属性读取，与项目其他地方保持一致）
    const currentLang = document.documentElement.lang || 'zh';

    // 多语言映射表
    const translations = {
        zh: {
            'login': '登录',
            'register': '注册',
            'logging_in': '登录中...',
            'registering': '注册中...',
            'success_login': '登录成功',
            'success_register': '注册成功',
            'error_password_required': '请输入密码',
            'error_email_required': '请输入邮箱或手机号',
            'error_username_required': '请输入用户名',
            'error_account_required': '请输入账号',
            'error_invalid_email': '邮箱或手机号格式不正确',
            'error_password_mismatch': '两次输入的密码不一致',
            'error_login_failed': '登录失败，请稍后重试',
            'error_register_failed': '注册失败，请稍后重试',
            'error_network': '网络错误，请检查网络连接',
            'error_account_not_found': '账号不存在',
            'error_wrong_password': '密码错误',
            'success_logout': '退出成功',
            'error_logout_failed': '退出失败',
            // 账号菜单相关
            'menu_profile': '账号信息',
            'menu_language': '选择语言',
            'menu_password': '设置密码',
            'menu_upload_app': '上传网页',
            'menu_my_apps': '我的文章',
            'menu_logout': '退出登录',
            // 账号信息模态框
            'modal_profile_title': '账号信息',
            'label_basic_info': '基本信息',
            'label_account': '账号',
            'label_register_time': '注册时间',
            'label_current_plan': '当前版本',
            'label_membership_info': '会员信息',
            'label_start_time': '生效时间',
            'label_expire_time': '过期时间',
            'label_web_quota': '网页额度',
            'label_view_limit': '浏览上限',
            'label_orders': '订单列表',
            'label_order_no': '订单号',
            'label_created_at': '创建时间',
            'no_orders': '暂无订单记录',
            'btn_upgrade': '升级套餐',
            // 设置密码模态框
            'modal_password_title': '设置密码',
            'label_old_password': '原密码',
            'placeholder_old_password': '请输入原密码（如未设置可留空）',
            'label_new_password': '新密码',
            'placeholder_new_password': '请输入新密码（1-200个字符）',
            'label_confirm_password': '确认新密码',
            'placeholder_confirm_password': '请再次输入新密码（1-200个字符）',
            'btn_cancel': '取消',
            'btn_confirm': '确定',
            'msg_password_set_success': '密码设置成功',
            'msg_password_set_failed': '密码设置失败',
            'msg_network_error': '网络错误，请重试',
            'msg_system_error': '系统错误，请重试',
            'msg_enter_new_password': '请输入新密码',
            'msg_password_min_length': '密码长度至少1位',
            'msg_password_max_length': '密码长度不能超过200个字符',
            'msg_password_mismatch': '两次输入的密码不一致',
            // 账号信息动态内容
            'text_unknown': '未知',
            'text_per_day': '/天',
            'plan_free': '免费版',
            'plan_basic': '基础版',
            'plan_pro': '专业版',
            'plan_premium': '高级版',
            'order_status_pending': '待支付',
            'order_status_paid': '已支付',
            'order_status_cancelled': '已取消',
            'order_status_refunded': '已退款'
        },
        en: {
            'login': 'Login',
            'register': 'Register',
            'logging_in': 'Logging in...',
            'registering': 'Registering...',
            'success_login': 'Login successful',
            'success_register': 'Registration successful',
            'error_password_required': 'Please enter password',
            'error_email_required': 'Please enter email or phone number',
            'error_username_required': 'Please enter username',
            'error_account_required': 'Please enter account',
            'error_invalid_email': 'Invalid email or phone format',
            'error_password_mismatch': 'Passwords do not match',
            'error_login_failed': 'Login failed, please try again later',
            'error_register_failed': 'Registration failed, please try again later',
            'error_network': 'Network error, please check your connection',
            'error_account_not_found': 'Account not found',
            'error_wrong_password': 'Wrong password',
            'success_logout': 'Logout successful',
            'error_logout_failed': 'Logout failed',
            // Account menu
            'menu_profile': 'Account Info',
            'menu_language': 'Language',
            'menu_password': 'Set Password',
            'menu_upload_app': 'Upload Web',
            'menu_my_apps': 'My Articles',
            'menu_logout': 'Logout',
            // Account profile modal
            'modal_profile_title': 'Account Information',
            'label_basic_info': 'Basic Information',
            'label_account': 'Account',
            'label_register_time': 'Registration Time',
            'label_current_plan': 'Current Plan',
            'label_membership_info': 'Membership Info',
            'label_start_time': 'Start Time',
            'label_expire_time': 'Expire Time',
            'label_web_quota': 'Web Quota',
            'label_view_limit': 'View Limit',
            'label_orders': 'Orders',
            'label_order_no': 'Order No.',
            'label_created_at': 'Created At',
            'no_orders': 'No orders yet',
            'btn_upgrade': 'Upgrade Plan',
            // Set password modal
            'modal_password_title': 'Set Password',
            'label_old_password': 'Old Password',
            'placeholder_old_password': 'Enter old password (leave blank if not set)',
            'label_new_password': 'New Password',
            'placeholder_new_password': 'Enter new password (1-200 characters)',
            'label_confirm_password': 'Confirm New Password',
            'placeholder_confirm_password': 'Re-enter new password (1-200 characters)',
            'btn_cancel': 'Cancel',
            'btn_confirm': 'Confirm',
            'msg_password_set_success': 'Password set successfully',
            'msg_password_set_failed': 'Failed to set password',
            'msg_network_error': 'Network error, please try again',
            'msg_system_error': 'System error, please try again',
            'msg_enter_new_password': 'Please enter new password',
            'msg_password_min_length': 'Password must be at least 1 character',
            'msg_password_max_length': 'Password cannot exceed 200 characters',
            'msg_password_mismatch': 'Passwords do not match',
            // Account profile dynamic content
            'text_unknown': 'Unknown',
            'text_per_day': '/day',
            'plan_free': 'Free',
            'plan_basic': 'Basic',
            'plan_pro': 'Pro',
            'plan_premium': 'Premium',
            'order_status_pending': 'Pending',
            'order_status_paid': 'Paid',
            'order_status_cancelled': 'Cancelled',
            'order_status_refunded': 'Refunded'
        }
    };

    // 返回对应语言的翻译，如果不存在则返回键名
    return translations[currentLang]?.[key] || translations['zh'][key] || key;
}

/**
 * 翻译套餐名称
 * @param {string} planName - 原始套餐名称
 * @return {string} - 翻译后的套餐名称
 */
function translatePlanName(planName) {
    if (!planName) return getTranslation('plan_free');

    const planMap = {
        '免费版': 'plan_free',
        '基础版': 'plan_basic',
        '专业版': 'plan_pro',
        '高级版': 'plan_premium',
        'Free': 'plan_free',
        'Basic': 'plan_basic',
        'Pro': 'plan_pro',
        'Premium': 'plan_premium'
    };

    const key = planMap[planName];
    return key ? getTranslation(key) : planName;
}

/**
 * 翻译订单状态
 * @param {number} status - 订单状态码 (0:待支付, 1:已支付, 2:已取消, 3:已退款)
 * @return {string} - 翻译后的状态文本
 */
function translateOrderStatus(status) {
    const statusKeys = [
        'order_status_pending',
        'order_status_paid',
        'order_status_cancelled',
        'order_status_refunded'
    ];

    const key = statusKeys[status];
    return key ? getTranslation(key) : getTranslation('text_unknown');
}

/**
 * 显示 Toast 消息
 * 使用 common.js 中的统一 showToast 函数
 * @param {string} message - 消息内容
 * @param {string} type - 消息类型：'success' 或 'error'
 * @param {number} duration - 显示时长（毫秒），默认 2500ms
 */
// ✅ 不再定义 showToast，直接使用 common.js 中的全局函数

/**
 * 处理用户登录
 */
async function handleLogin() {
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;
    const rememberAccount = document.getElementById('rememberAccount').checked;

    // 验证输入
    if (!username) {
        showToast(getTranslation('error_account_required'), 'error');
        return;
    }

    // 注意：不再强制要求密码，因为有些老用户可能没有设置密码

    try {
        // 禁用按钮，显示加载状态
        const submitBtn = document.querySelector('.submit-btn');
        const originalText = submitBtn.textContent;
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="loading"></span>' + getTranslation('logging_in');

        // 发送登录请求
        const response = await fetch('/account/api/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                username: username,
                password: password
            })
        });

        const data = await response.json();

        if (data.status === 'success') {
            // 显示成功消息（更长时间，让用户看清楚）
            showToast(data.message || getTranslation('success_login'), 'success', 2000);

            // 如果选择记住账号，保存到 localStorage
            if (rememberAccount) {
                localStorage.setItem('remembered_username', username);
            } else {
                localStorage.removeItem('remembered_username');
            }

            // 按钮显示成功状态
            submitBtn.innerHTML = '<span style="margin-right: 8px;">✓</span>' + getTranslation('success_login');
            submitBtn.style.background = 'linear-gradient(135deg, #10b981 0%, #059669 100%)';

            // 延迟跳转，让用户看到成功消息
            var redirectUrlEl = document.getElementById('redirectUrl');
            var redirectUrl = redirectUrlEl ? redirectUrlEl.value : '';
            setTimeout(() => {
                window.location.href = redirectUrl || '/';
            }, 1500);
        } else {
            showToast(data.message || getTranslation('error_login_failed'), 'error');
            submitBtn.disabled = false;
            submitBtn.textContent = originalText;
        }

    } catch (error) {
        console.error('登录错误:', error);
        showToast(getTranslation('error_network'), 'error');

        // 恢复按钮状态
        const submitBtn = document.querySelector('.submit-btn');
        submitBtn.disabled = false;
        submitBtn.textContent = getTranslation('login');
    }
}

/**
 * 处理用户注册
 */
async function handleRegister() {
    const account = document.getElementById('email').value.trim();
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;
    const confirmPassword = document.getElementById('confirmPassword').value;

    // 验证输入
    if (!account) {
        showToast(getTranslation('error_email_required'), 'error');
        return;
    }

    // 验证邮箱或手机号格式
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    const phoneRegex = /^1\d{10}$/;
    const isEmail = account.includes('@');

    if (isEmail) {
        // 邮箱格式验证
        if (!emailRegex.test(account)) {
            showToast(getTranslation('error_invalid_email'), 'error');
            return;
        }
    } else {
        // 手机号格式验证（11位，以1开头）
        if (!phoneRegex.test(account)) {
            showToast(getTranslation('error_invalid_email'), 'error');
            return;
        }
    }

    if (!username) {
        showToast(getTranslation('error_username_required'), 'error');
        return;
    }

    // 如果提供了密码，需要确认
    if (password && password !== confirmPassword) {
        showToast(getTranslation('error_password_mismatch'), 'error');
        return;
    }

    try {
        // 禁用按钮，显示加载状态
        const submitBtn = document.querySelector('.submit-btn');
        const originalText = submitBtn.textContent;
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="loading"></span>' + getTranslation('registering');

        // 发送注册请求
        const response = await fetch('/account/api/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                email: account,
                username: username,
                password: password
            })
        });

        const data = await response.json();

        if (data.status === 'success') {
            // 显示成功消息
            showToast(data.message || getTranslation('success_register'), 'success', 2000);

            // 按钮显示成功状态
            submitBtn.innerHTML = '<span style="margin-right: 8px;">✓</span>' + getTranslation('success_register');
            submitBtn.style.background = 'linear-gradient(135deg, #10b981 0%, #059669 100%)';

            // 延迟跳转到登录页面
            setTimeout(() => {
                window.location.href = '/account/login';
            }, 1500);
        } else {
            showToast(data.message || getTranslation('error_register_failed'), 'error');
            submitBtn.disabled = false;
            submitBtn.textContent = originalText;
        }

    } catch (error) {
        console.error('注册错误:', error);
        showToast(getTranslation('error_network'), 'error');

        // 恢复按钮状态
        const submitBtn = document.querySelector('.submit-btn');
        submitBtn.disabled = false;
        submitBtn.textContent = getTranslation('register');
    }
}

/**
 * 检查登录状态
 * @returns {Promise<Object>} - 包含 isLoggedIn 和用户信息的对象
 */
async function checkLoginStatus() {
    try {
        const response = await fetch('/account/api/check_login');
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('检查登录状态失败:', error);
        return { isLoggedIn: false, user: null };
    }
}

/**
 * 处理用户登出
 */
async function handleLogout() {
    try {
        // ⭐ 用页面跳转代替 fetch，确保浏览器 100% 处理 Set-Cookie
        window.location.href = '/account/api/logout?redirect=' + encodeURIComponent(window.location.origin + '/');
    } catch (error) {
        console.error('登出错误:', error);
        showToast(getTranslation('error_network'), 'error');
    }
}

/**
 * 页面加载时初始化
 */
document.addEventListener('DOMContentLoaded', function() {
    // 如果是登录页面，尝试填充记住的用户名
    if (window.location.pathname.includes('/account/login')) {
        const rememberedUsername = localStorage.getItem('remembered_username');
        if (rememberedUsername) {
            const usernameInput = document.getElementById('username');
            if (usernameInput) {
                usernameInput.value = rememberedUsername;
            }
        }
    }

    // 如果是注册页面，添加邮箱到用户名的自动填充功能
    if (window.location.pathname.includes('/account/register')) {
        const emailInput = document.getElementById('email');
        const usernameInput = document.getElementById('username');

        if (emailInput && usernameInput) {
            // 当用户名输入框获得焦点且为空时，自动填充邮箱前缀
            usernameInput.addEventListener('focus', function() {
                if (!this.value.trim()) {
                    const email = emailInput.value.trim();
                    if (email) {
                        // 提取邮箱@前面的部分作为默认用户名
                        const usernameFromEmail = email.split('@')[0];
                        this.value = usernameFromEmail;
                    }
                }
            });
        }
    }

    // 添加回车键提交支持 - 用户名输入框
    const usernameInput = document.getElementById('username');
    if (usernameInput) {
        usernameInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                if (window.location.pathname.includes('/account/login')) {
                    handleLogin();
                } else if (window.location.pathname.includes('/account/register')) {
                    handleRegister();
                }
            }
        });
    }

    // 添加回车键提交支持 - 密码输入框
    const passwordInput = document.getElementById('password');
    if (passwordInput) {
        passwordInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                if (window.location.pathname.includes('/account/login')) {
                    handleLogin();
                } else if (window.location.pathname.includes('/account/register')) {
                    handleRegister();
                }
            }
        });
    }

    // 添加提交按钮点击事件支持（替代 onclick，修复平板点击无反应问题）
    const submitBtn = document.querySelector('.submit-btn');
    if (submitBtn) {
        submitBtn.addEventListener('click', function(e) {
            if (window.location.pathname.includes('/account/login')) {
                handleLogin();
            } else if (window.location.pathname.includes('/account/register')) {
                handleRegister();
            }
        });
    }
});

/**
 * 显示账号操作下拉菜单
 * @param {Event} event - 点击事件
 */
function showAccountMenu(event) {
    event.preventDefault();
    event.stopPropagation();

    // 获取触发元素
    const triggerElement = event.currentTarget || event.target;
    if (!triggerElement) {
        console.error('无法获取触发元素');
        return;
    }

    // 立即获取位置信息（在异步操作之前）
    const rect = triggerElement.getBoundingClientRect();

    // 检查是否已登录
    fetch('/account/api/check_login', { credentials: 'include' })
        .then(res => res.json())
        .then(data => {
            if (!data.isLoggedIn || !data.user) {
                showToast('请先登录', 'error');
                return;
            }

            // 如果已有菜单，先关闭
            const existingMenu = document.getElementById('accountDropdownMenu');
            if (existingMenu) {
                console.log('已存在账号菜单，移除');
                existingMenu.remove();
                return;
            }

            console.log('创建新的账号菜单');

            // 创建下拉菜单
            const menu = document.createElement('div');
            menu.id = 'accountDropdownMenu';
            menu.style.cssText = `
                position: fixed;
                top: ${rect.bottom + 5}px;
                right: ${window.innerWidth - rect.right}px;
                background: white;
                border-radius: 8px;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
                min-width: 160px;
                z-index: 10000;
                overflow: hidden;
                animation: dropdownFadeIn 0.2s ease;
            `;

            // 添加CSS动画
            if (!document.getElementById('dropdownMenuStyles')) {
                const style = document.createElement('style');
                style.id = 'dropdownMenuStyles';
                style.textContent = `
                    @keyframes dropdownFadeIn {
                        from {
                            opacity: 0;
                            transform: translateY(-10px);
                        }
                        to {
                            opacity: 1;
                            transform: translateY(0);
                        }
                    }
                    .account-menu-item {
                        padding: 12px 16px;
                        cursor: pointer;
                        transition: all 0.2s ease;
                        display: flex;
                        align-items: center;
                        gap: 10px;
                        color: #333;
                        font-size: 14px;
                        border: none;
                        background: none;
                        width: 100%;
                        text-align: left;
                    }
                    .account-menu-item i {
                        font-size: 18px;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                    }
                    .account-menu-item:hover {
                        background: #f5f5f5;
                    }
                    .account-menu-item.danger {
                        color: #ef4444;
                    }
                    .account-menu-item.danger:hover {
                        background: #fee2e2;
                    }
                    .menu-divider {
                        height: 1px;
                        background: #eee;
                        margin: 4px 0;
                    }
                `;
                document.head.appendChild(style);
            }

            // 创建菜单项
            menu.innerHTML = `
                <button class="account-menu-item" data-action="profile">
                    <i class="ri-user-line"></i>
                    <span>${getTranslation('menu_profile')}</span>
                </button>
                <button class="account-menu-item" data-action="language">
                    <i class="ri-global-line"></i>
                    <span>${getTranslation('menu_language')}</span>
                </button>
                <button class="account-menu-item" data-action="password">
                    <i class="ri-lock-line"></i>
                    <span>${getTranslation('menu_password')}</span>
                </button>
                <button class="account-menu-item" data-action="upload-app">
                    <i class="ri-upload-cloud-line"></i>
                    <span>${getTranslation('menu_upload_app')}</span>
                </button>
                <button class="account-menu-item" data-action="my-apps">
                    <i class="ri-global-line"></i>
                    <span>${getTranslation('menu_my_apps')}</span>
                </button>
                <div class="menu-divider"></div>
                <button class="account-menu-item danger" data-action="logout">
                    <i class="ri-logout-box-r-line"></i>
                    <span>${getTranslation('menu_logout')}</span>
                </button>
            `;

            document.body.appendChild(menu);

            // 绑定菜单项点击事件
            menu.querySelectorAll('.account-menu-item').forEach(item => {
                item.addEventListener('click', function(e) {
                    e.stopPropagation();
                    const action = this.dataset.action;

                    console.log('菜单项点击，action:', action);

                    // 特殊处理：选择语言时不移除账号菜单
                    if (action === 'language') {
                        console.log('执行: toggleLanguageMenu');
                        toggleLanguageMenu(triggerElement);
                        return; // 不移除菜单，直接返回
                    }

                    // 其他操作：关闭下拉菜单
                    menu.remove();

                    // 执行对应操作
                    switch(action) {
                        case 'profile':
                            console.log('执行: showAccountProfileModal');
                            showAccountProfileModal();
                            break;
                        case 'password':
                            console.log('执行: showSetPasswordModal');
                            showSetPasswordModal();
                            break;
                        case 'logout':
                            handleLogout();
                            break;
                        case 'upload-app':
                            window.location.href = '/apps/upload';
                            break;
                        case 'my-apps':
                            window.location.href = '/home';
                            break;
                    }
                });
            });

            // 点击其他地方关闭菜单
            setTimeout(() => {
                document.addEventListener('click', function closeMenu(e) {
                    if (!menu.contains(e.target)) {
                        menu.remove();
                        document.removeEventListener('click', closeMenu);
                    }
                });
            }, 0);
        })
        .catch(error => {
            console.error('检查登录状态失败:', error);
            showToast('网络错误', 'error');
        });
}

/**
 * 切换语言选择菜单
 * @param {HTMLElement} triggerElement - 触发元素
 */
function toggleLanguageMenu(triggerElement) {
    // 检查是否已有语言子菜单
    const existingLangMenu = document.getElementById('languageSubMenu');
    if (existingLangMenu) {
        console.log('已存在语言子菜单，移除');
        existingLangMenu.remove();
        return;
    }

    // 获取账号菜单位置
    const accountMenu = document.getElementById('accountDropdownMenu');
    if (!accountMenu) {
        console.error('❌ 找不到 accountDropdownMenu');
        return;
    }

    console.log('✅ 找到 accountDropdownMenu');

    const menuRect = accountMenu.getBoundingClientRect();

    // 创建语言子菜单 - 改为在账号菜单右侧显示
    const langMenu = document.createElement('div');
    langMenu.id = 'languageSubMenu';
    langMenu.style.cssText = `
        position: fixed;
        top: ${menuRect.top}px;
        left: ${menuRect.right + 5}px;
        background: white;
        border-radius: 8px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
        min-width: 140px;
        z-index: 10002;
        overflow: hidden;
        animation: dropdownFadeIn 0.2s ease;
    `;

    // 如果右侧空间不足，则显示在左侧
    if (menuRect.right + 150 > window.innerWidth) {
        langMenu.style.left = `${menuRect.left - 145}px`;
    }

    // 获取当前语言
    const currentLang = document.cookie.split('; ').find(row => row.startsWith('language='))?.split('=')[1] || 'zh';

    langMenu.innerHTML = `
        <button class="account-menu-item ${currentLang === 'zh' ? 'selected' : ''}" data-lang="zh" style="${currentLang === 'zh' ? 'background: #f0f7ff; color: #2563eb;' : ''}">
            <span>🇨🇳</span>
            <span>中文</span>
            ${currentLang === 'zh' ? '<span style="margin-left: auto; color: #2563eb;">✓</span>' : ''}
        </button>
        <button class="account-menu-item ${currentLang === 'en' ? 'selected' : ''}" data-lang="en" style="${currentLang === 'en' ? 'background: #f0f7ff; color: #2563eb;' : ''}">
            <span>🇬🇧</span>
            <span>English</span>
            ${currentLang === 'en' ? '<span style="margin-left: auto; color: #2563eb;">✓</span>' : ''}
        </button>
    `;

    document.body.appendChild(langMenu);

    // 绑定语言选项点击事件
    langMenu.querySelectorAll('.account-menu-item').forEach(item => {
        item.addEventListener('click', function(e) {
            e.stopPropagation();
            const lang = this.dataset.lang;
            switchLanguage(lang);
        });
    });

    // 点击其他地方关闭菜单
    setTimeout(() => {
        document.addEventListener('click', function closeLangMenu(e) {
            if (!langMenu.contains(e.target) && !e.target.closest('[data-action="language"]')) {
                langMenu.remove();
                document.removeEventListener('click', closeLangMenu);
            }
        });
    }, 0);
}

/**
 * 切换语言
 * @param {string} lang - 语言代码 ('zh' 或 'en')
 */
async function switchLanguage(lang) {
    try {
        // 保存语言到 cookie
        document.cookie = `language=${lang}; path=/; max-age=31536000`;

        // 调用 API 保存语言偏好
        await fetch('/api/set-language', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({language: lang})
        });

        // 关闭所有菜单
        const langMenu = document.getElementById('languageSubMenu');
        if (langMenu) langMenu.remove();

        const accountMenu = document.getElementById('accountDropdownMenu');
        if (accountMenu) accountMenu.remove();

        // 显示提示
        showToast(lang === 'zh' ? '语言已切换为中文' : 'Language switched to English', 'success');

        // 延迟刷新页面
        setTimeout(() => {
            window.location.reload();
        }, 800);
    } catch (error) {
        console.error('切换语言失败:', error);
        showToast('切换语言失败', 'error');
    }
}

/**
 * 显示账号信息模态框
 */
async function showAccountProfileModal() {
    // 创建遮罩层
    const overlay = document.createElement('div');
    overlay.id = 'accountProfileOverlay';
    overlay.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.5);
        z-index: 10001;
        display: flex;
        justify-content: center;
        align-items: center;
    `;

    // 创建模态框容器
    const modalContainer = document.createElement('div');
    modalContainer.id = 'accountProfileModal';
    modalContainer.style.cssText = `
        background: white;
        border-radius: 12px;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
        max-width: 500px;
        width: 90%;
        max-height: 80vh;
        overflow-y: auto;
        position: relative;
    `;

    // 创建模态框头部
    const header = document.createElement('div');
    header.style.cssText = `
        padding: 20px;
        border-bottom: 1px solid #eee;
        display: flex;
        justify-content: space-between;
        align-items: center;
    `;

    const title = document.createElement('h3');
    title.textContent = getTranslation('modal_profile_title');
    title.style.cssText = `
        margin: 0;
        color: #333;
        font-size: 18px;
    `;

    const closeBtn = document.createElement('button');
    closeBtn.innerHTML = '&times;';
    closeBtn.style.cssText = `
        background: none;
        border: none;
        font-size: 24px;
        cursor: pointer;
        color: #999;
        padding: 0;
        width: 30px;
        height: 30px;
        display: flex;
        align-items: center;
        justify-content: center;
    `;
    closeBtn.onclick = () => {
        document.body.removeChild(overlay);
    };

    header.appendChild(title);
    header.appendChild(closeBtn);

    // 创建内容区域
    const content = document.createElement('div');
    content.id = 'accountProfileContent';
    content.style.cssText = `
        padding: 20px;
    `;

    // 添加加载状态
    content.innerHTML = '<div style="text-align: center; padding: 20px;">加载中...</div>';

    modalContainer.appendChild(header);
    modalContainer.appendChild(content);
    overlay.appendChild(modalContainer);
    document.body.appendChild(overlay);

    // 点击遮罩层关闭
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) {
            document.body.removeChild(overlay);
        }
    });

    // 加载用户信息
    loadUserProfile(content);
}

/**
 * 显示设置密码模态框
 */
function showSetPasswordModal() {
    // 创建遮罩层
    const overlay = document.createElement('div');
    overlay.id = 'setPasswordOverlay';
    overlay.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.5);
        z-index: 10001;
        display: flex;
        justify-content: center;
        align-items: center;
    `;

    // 创建模态框容器
    const modalContainer = document.createElement('div');
    modalContainer.id = 'setPasswordModal';
    modalContainer.style.cssText = `
        background: white;
        border-radius: 12px;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
        max-width: 450px;
        width: 90%;
        position: relative;
    `;

    // 创建模态框头部
    const header = document.createElement('div');
    header.style.cssText = `
        padding: 20px;
        border-bottom: 1px solid #eee;
        display: flex;
        justify-content: space-between;
        align-items: center;
    `;

    const title = document.createElement('h3');
    title.textContent = getTranslation('modal_password_title');
    title.style.cssText = `
        margin: 0;
        color: #333;
        font-size: 18px;
    `;

    const closeBtn = document.createElement('button');
    closeBtn.innerHTML = '&times;';
    closeBtn.style.cssText = `
        background: none;
        border: none;
        font-size: 24px;
        cursor: pointer;
        color: #999;
        padding: 0;
        width: 30px;
        height: 30px;
        display: flex;
        align-items: center;
        justify-content: center;
    `;
    closeBtn.onclick = () => {
        document.body.removeChild(overlay);
    };

    header.appendChild(title);
    header.appendChild(closeBtn);

    // 创建表单内容
    const content = document.createElement('div');
    content.style.cssText = `
        padding: 20px;
    `;

    content.innerHTML = `
        <form id="setPasswordForm">
            <div style="margin-bottom: 15px;">
                <label style="display: block; margin-bottom: 5px; color: #666; font-size: 14px;">${getTranslation('label_old_password')}</label>
                <input type="password" id="oldPassword" style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px;" placeholder="${getTranslation('placeholder_old_password')}">
            </div>
            <div style="margin-bottom: 15px;">
                <label style="display: block; margin-bottom: 5px; color: #666; font-size: 14px;">${getTranslation('label_new_password')}</label>
                <input type="password" id="newPassword" style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px;" placeholder="${getTranslation('placeholder_new_password')}" required maxlength="200">
            </div>
            <div style="margin-bottom: 20px;">
                <label style="display: block; margin-bottom: 5px; color: #666; font-size: 14px;">${getTranslation('label_confirm_password')}</label>
                <input type="password" id="confirmPassword" style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px;" placeholder="${getTranslation('placeholder_confirm_password')}" required maxlength="200">
            </div>
            <div style="display: flex; gap: 10px;">
                <button type="button" id="cancelSetPassword" style="flex: 1; padding: 10px; background: #f5f5f5; color: #666; border: none; border-radius: 6px; cursor: pointer; font-size: 14px;">
                    ${getTranslation('btn_cancel')}
                </button>
                <button type="submit" style="flex: 1; padding: 10px; background: #667eea; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 14px;">
                    ${getTranslation('btn_confirm')}
                </button>
            </div>
        </form>
    `;

    modalContainer.appendChild(header);
    modalContainer.appendChild(content);
    overlay.appendChild(modalContainer);
    document.body.appendChild(overlay);

    // 点击遮罩层关闭
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) {
            document.body.removeChild(overlay);
        }
    });

    // 绑定取消按钮
    const cancelBtn = document.getElementById('cancelSetPassword');
    if (cancelBtn) {
        cancelBtn.addEventListener('click', () => {
            document.body.removeChild(overlay);
        });
    }

    // 绑定确定按钮（直接使用按钮点击事件，而不是表单提交）
    const submitBtn = content.querySelector('button[type="submit"]');
    if (submitBtn) {
        console.log('找到确定按钮，绑定点击事件');
        submitBtn.addEventListener('click', async (e) => {
            e.preventDefault();
            console.log('确定按钮被点击');
            await handleSetPassword();
        });
    } else {
        console.error('找不到确定按钮');
    }
}

/**
 * 处理设置密码
 */
async function handleSetPassword() {
    console.log('handleSetPassword 被调用');

    const oldPasswordEl = document.getElementById('oldPassword');
    const newPasswordEl = document.getElementById('newPassword');
    const confirmPasswordEl = document.getElementById('confirmPassword');

    if (!oldPasswordEl || !newPasswordEl || !confirmPasswordEl) {
        console.error('找不到密码输入框元素');
        showToast(getTranslation('msg_system_error'), 'error');
        return;
    }

    const oldPassword = oldPasswordEl.value;
    const newPassword = newPasswordEl.value;
    const confirmPassword = confirmPasswordEl.value;

    console.log('密码输入:', { oldPassword: oldPassword ? '***' : '(空)', newPassword: newPassword ? '***' : '(空)', confirmPassword: confirmPassword ? '***' : '(空)' });

    // 验证输入
    console.log('开始验证...');

    if (!newPassword) {
        console.log('验证失败: 新密码为空');
        showToast(getTranslation('msg_enter_new_password'), 'error');
        return;
    }

    console.log('新密码长度:', newPassword.length);

    if (newPassword.length < 1) {
        console.log('验证失败: 密码长度小于1');
        showToast(getTranslation('msg_password_min_length'), 'error');
        return;
    }

    if (newPassword.length > 200) {
        console.log('验证失败: 密码长度超过200');
        showToast(getTranslation('msg_password_max_length'), 'error');
        return;
    }

    console.log('比较两次密码:', { new: newPassword.length, confirm: confirmPassword.length, match: newPassword === confirmPassword });

    if (newPassword !== confirmPassword) {
        console.log('验证失败: 两次密码不一致');
        showToast(getTranslation('msg_password_mismatch'), 'error');
        return;
    }

    console.log('✅ 验证通过，开始调用API...');

    try {
        const response = await fetch('/account/api/set_password', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                old_password: oldPassword,
                new_password: newPassword
            })
        });

        console.log('API响应状态:', response.status);

        const data = await response.json();
        console.log('API响应数据:', data);

        if (data.status === 'success') {
            showToast(getTranslation('msg_password_set_success'), 'success');
            const overlay = document.getElementById('setPasswordOverlay');
            if (overlay) {
                document.body.removeChild(overlay);
            }
        } else {
            showToast(data.message || getTranslation('msg_password_set_failed'), 'error');
        }
    } catch (error) {
        console.error('设置密码错误:', error);
        showToast(getTranslation('msg_network_error'), 'error');
    }
}

/**
 * 加载用户详细信息
 * @param {HTMLElement} contentElement - 内容容器元素
 */
async function loadUserProfile(contentElement) {
    try {
        const response = await fetch('/account/api/profile');
        const data = await response.json();

        if (data.status !== 'success') {
            contentElement.innerHTML = `<div style="color: red; text-align: center;">${data.message || '获取用户信息失败'}</div>`;
            return;
        }

        const profile = data.data;

        // 构建用户信息HTML
        let html = `
            <div style="margin-bottom: 20px;">
                <h4 style="margin: 0 0 15px 0; color: #333;">${getTranslation('label_basic_info') || '基本信息'}</h4>
                <div style="display: grid; gap: 10px;">
                    <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #f0f0f0;">
                        <span style="color: #666;">${getTranslation('label_account')}：</span>
                        <span style="font-weight: 500;">${profile.username}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #f0f0f0;">
                        <span style="color: #666;">${getTranslation('label_register_time')}：</span>
                        <span>${profile.register_time || getTranslation('text_unknown')}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #f0f0f0;">
                        <span style="color: #666;">${getTranslation('label_current_plan')}：</span>
                        <span style="color: #667eea; font-weight: 500;">${translatePlanName(profile.current_plan)}</span>
                    </div>
                </div>
            </div>
        `;

        // 会员信息（如果有）
        if (profile.membership) {
            html += `
                <div style="margin-bottom: 20px;">
                    <h4 style="margin: 0 0 15px 0; color: #333;">${getTranslation('label_membership_info')}</h4>
                    <div style="display: grid; gap: 10px;">
                        <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #f0f0f0;">
                            <span style="color: #666;">${getTranslation('label_start_time')}：</span>
                            <span>${profile.membership.start_at || getTranslation('text_unknown')}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #f0f0f0;">
                            <span style="color: #666;">${getTranslation('label_expire_time')}：</span>
                            <span>${profile.membership.expire_at || getTranslation('text_unknown')}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #f0f0f0;">
                            <span style="color: #666;">${getTranslation('label_web_quota')}：</span>
                            <span>${profile.membership.web_quota_used}/${profile.membership.web_quota}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #f0f0f0;">
                            <span style="color: #666;">${getTranslation('label_view_limit')}：</span>
                            <span>${profile.membership.view_limit}${getTranslation('text_per_day')}</span>
                        </div>
                    </div>
                </div>
            `;
        }

        // 订单列表
        html += `
            <div style="margin-bottom: 20px;">
                <h4 style="margin: 0 0 15px 0; color: #333;">${getTranslation('label_orders')}</h4>
        `;

        if (profile.orders && profile.orders.length > 0) {
            html += '<div style="max-height: 200px; overflow-y: auto;">';
            profile.orders.forEach(order => {
                const statusText = translateOrderStatus(order.order_status);
                const statusColor = ['#ff9800', '#4caf50', '#9e9e9e', '#f44336'][order.order_status] || '#999';

                html += `
                    <div style="padding: 12px; border: 1px solid #eee; border-radius: 6px; margin-bottom: 10px;">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                            <span style="font-weight: 500;">${order.plan_name}</span>
                            <span style="color: ${statusColor}; font-size: 12px;">${statusText}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; font-size: 13px; color: #666;">
                            <span>${getTranslation('label_order_no')}：${order.order_no}</span>
                            <span>￥${order.amount.toFixed(2)}</span>
                        </div>
                        <div style="font-size: 12px; color: #999; margin-top: 5px;">
                            ${getTranslation('label_created_at')}：${order.created_at}
                        </div>
                    </div>
                `;
            });
            html += '</div>';
        } else {
            html += `<div style="text-align: center; color: #999; padding: 20px;">${getTranslation('no_orders')}</div>`;
        }

        html += '</div>';

        // 升级按钮
        html += `
            <div style="margin-top: 20px;">
                <button id="upgradePlanBtn" style="width: 100%; padding: 10px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 14px;">
                    ${getTranslation('btn_upgrade')}
                </button>
            </div>
        `;

        contentElement.innerHTML = html;

        // 绑定升级按钮事件
        document.getElementById('upgradePlanBtn').addEventListener('click', () => {
            window.location.href = '/price';
        });

    } catch (error) {
        console.error('加载用户信息失败:', error);
        contentElement.innerHTML = '<div style="color: red; text-align: center;">加载失败，请重试</div>';
    }
}

// 导出函数供其他模块使用
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        handleLogin,
        handleRegister,
        handleLogout,
        checkLoginStatus,
        showToast,
        showAccountMenu,
        loadUserProfile
    };
}
