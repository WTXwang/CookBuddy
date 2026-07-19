/* ============================================
   今晚吃什么 — 登录/注册（后端 MySQL + JWT）
   ============================================ */

const Auth = {

  currentUser: null,   // { username } or null
  API_BASE: 'http://localhost:8000',

  /* ======== 初始化 ======== */
  init() {
    // 恢复 session
    const token = localStorage.getItem('chef_token');
    const username = localStorage.getItem('chef_username');
    if (token && username) {
      this.currentUser = { username };
    }
    this._updateUI();

    // 事件
    document.getElementById('loginBtn').addEventListener('click', () => this.openModal());
    document.getElementById('authModalClose').addEventListener('click', () => this.closeModal());
    document.getElementById('authModal').addEventListener('click', (e) => {
      if (e.target === e.currentTarget) this.closeModal();
    });

    // Tab 切换
    document.querySelectorAll('.auth-tab').forEach(tab => {
      tab.addEventListener('click', () => this._switchTab(tab.dataset.tab));
    });

    // 登录提交
    document.getElementById('loginForm').addEventListener('submit', (e) => {
      e.preventDefault();
      this._login();
    });

    // 注册提交
    document.getElementById('registerForm').addEventListener('submit', (e) => {
      e.preventDefault();
      this._register();
    });
  },

  /* ======== API ======== */
  isLoggedIn() {
    return !!this.currentUser;
  },

  getUsername() {
    return this.currentUser ? this.currentUser.username : null;
  },

  getToken() {
    return localStorage.getItem('chef_token') || '';
  },

  logout() {
    this.currentUser = null;
    localStorage.removeItem('chef_token');
    localStorage.removeItem('chef_username');
    this._updateUI();
    if (typeof App !== 'undefined' && App._onLogout) {
      App._onLogout();
    }
  },

  /* ======== Modal ======== */
  openModal() {
    if (this.isLoggedIn()) {
      if (confirm('确定要退出登录吗？')) this.logout();
      return;
    }
    document.getElementById('authModal').classList.add('show');
    this._switchTab('login');
    document.getElementById('loginForm').reset();
    document.getElementById('registerForm').reset();
  },

  closeModal() {
    document.getElementById('authModal').classList.remove('show');
  },

  /* ======== Internal ======== */
  _switchTab(tab) {
    document.querySelectorAll('.auth-tab').forEach(t => t.classList.remove('active'));
    document.querySelector(`.auth-tab[data-tab="${tab}"]`).classList.add('active');
    document.getElementById('loginForm').classList.toggle('hidden', tab !== 'login');
    document.getElementById('registerForm').classList.toggle('hidden', tab !== 'register');
    document.getElementById('loginError').textContent = '';
    document.getElementById('registerError').textContent = '';
  },

  async _login() {
    const form = document.getElementById('loginForm');
    const username = form.loginUser.value.trim();
    const password = form.loginPass.value;
    const errorEl = document.getElementById('loginError');

    if (!username || !password) {
      errorEl.textContent = '请填写用户名和密码';
      return;
    }

    try {
      const resp = await fetch(`${this.API_BASE}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      const data = await resp.json();
      if (!resp.ok) {
        errorEl.textContent = data.detail || '登录失败';
        return;
      }

      this.currentUser = { username: data.username };
      localStorage.setItem('chef_token', data.access_token);
      localStorage.setItem('chef_username', data.username);
      this._updateUI();
      this.closeModal();

      if (typeof App !== 'undefined' && App._onLogin) {
        App._onLogin(data.username);
      }
    } catch (e) {
      errorEl.textContent = '网络错误，请检查后端是否启动';
    }
  },

  async _register() {
    const form = document.getElementById('registerForm');
    const username = form.regUser.value.trim();
    const password = form.regPass.value;
    const password2 = form.regPass2.value;
    const errorEl = document.getElementById('registerError');

    if (!username || !password) {
      errorEl.textContent = '请填写用户名和密码';
      return;
    }
    if (username.length < 2) {
      errorEl.textContent = '用户名至少2个字符';
      return;
    }
    if (password.length < 6) {
      errorEl.textContent = '密码至少6位';
      return;
    }
    if (password !== password2) {
      errorEl.textContent = '两次密码不一致';
      return;
    }

    try {
      const resp = await fetch(`${this.API_BASE}/api/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      const data = await resp.json();
      if (!resp.ok) {
        errorEl.textContent = data.detail || '注册失败';
        return;
      }

      this.currentUser = { username: data.username };
      localStorage.setItem('chef_token', data.access_token);
      localStorage.setItem('chef_username', data.username);
      this._updateUI();
      this.closeModal();

      if (typeof App !== 'undefined' && App._onLogin) {
        App._onLogin(data.username);
      }
    } catch (e) {
      errorEl.textContent = '网络错误，请检查后端是否启动';
    }
  },

  _updateUI() {
    const btn = document.getElementById('loginBtn');
    if (!btn) return;
    if (this.isLoggedIn()) {
      btn.classList.add('logged-in');
      btn.querySelector('.login-btn-icon').textContent = '👨‍🍳';
      btn.querySelector('.login-btn-text').textContent = this.getUsername();
    } else {
      btn.classList.remove('logged-in');
      btn.querySelector('.login-btn-icon').textContent = '👤';
      btn.querySelector('.login-btn-text').textContent = '登录';
    }
  }
};
