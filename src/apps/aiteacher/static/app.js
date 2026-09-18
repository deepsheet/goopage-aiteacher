(() => {
  'use strict';

  const course = JSON.parse(document.getElementById('courseData').textContent);
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const storageKey = 'aiteacher-demo-state-v1';
  const initialGreeting = 'AI老师';

  const state = {
    lessonIndex: 0,
    completed: new Set(),
    lastAction: '',
    constructedPhrase: [],
    attempts: 0,
    busy: false,
    autoVoice: true,
    quiet: false,
    materialMode: false,
    material: null,
    account: { isLoggedIn: false, user: null },
    preferences: { name: '', modes: [], interests: '', speechRate: 0.86 },
    messages: [{ role: 'assistant', content: initialGreeting }],
  };

  let mediaRecorder = null;
  let mediaStream = null;
  let audioChunks = [];
  let recordStartedAt = 0;
  let recordTimer = null;
  let waitTimer = null;

  function restoreState() {
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey) || '{}');
      state.lessonIndex = Math.max(0, Math.min(course.lessons.length - 1, Number(saved.lessonIndex) || 0));
      state.completed = new Set(Array.isArray(saved.completed) ? saved.completed : []);
      state.attempts = Number(saved.attempts) || 0;
      state.autoVoice = saved.autoVoice !== false;
      state.quiet = Boolean(saved.quiet);
      state.preferences = { ...state.preferences, ...(saved.preferences || {}) };
    } catch (_) { /* A fresh state is safe when browser storage is unavailable. */ }
  }

  function persistState() {
    try {
      localStorage.setItem(storageKey, JSON.stringify({
        lessonIndex: state.lessonIndex,
        completed: [...state.completed],
        attempts: state.attempts,
        autoVoice: state.autoVoice,
        quiet: state.quiet,
        preferences: state.preferences,
      }));
    } catch (_) { /* The lesson remains usable without persistence. */ }
  }

  function escapeHtml(value) {
    const node = document.createElement('div');
    node.textContent = String(value || '');
    return node.innerHTML;
  }

  function showToast(message) {
    const toast = $('#toast');
    toast.textContent = message;
    toast.classList.add('show');
    window.clearTimeout(showToast.timer);
    showToast.timer = window.setTimeout(() => toast.classList.remove('show'), 2300);
  }

  function speak(text, force = false) {
    if ((!state.autoVoice && !force) || state.quiet || !('speechSynthesis' in window) || !text) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text.replace(/[*#`]/g, ''));
    utterance.lang = 'zh-CN';
    utterance.rate = Number(state.preferences.speechRate) || 0.86;
    utterance.pitch = 1.02;
    const voices = window.speechSynthesis.getVoices();
    const chineseVoice = voices.find(voice => /^zh/i.test(voice.lang));
    if (chineseVoice) utterance.voice = chineseVoice;
    window.speechSynthesis.speak(utterance);
  }

  function currentLesson() { return course.lessons[state.lessonIndex]; }

  function activeContextTitle() {
    return state.materialMode && state.material ? state.material.title : currentLesson().title;
  }

  function updateProgress() {
    const total = course.lessons.length;
    $('#progressLabel').textContent = `${state.lessonIndex + 1} / ${total}`;
    $('#progressFill').style.width = `${((state.lessonIndex + 1) / total) * 100}%`;
    $('#progressTrack').setAttribute('aria-valuenow', String(state.lessonIndex + 1));
    $('#attemptCount').textContent = `${state.attempts} 次主动表达`;
    $$('.lesson-tab').forEach((tab, index) => {
      const lesson = course.lessons[index];
      tab.classList.toggle('active', index === state.lessonIndex);
      tab.classList.toggle('completed', state.completed.has(lesson.id));
      tab.setAttribute('aria-current', index === state.lessonIndex ? 'step' : 'false');
      if (!state.completed.has(lesson.id)) {
        const number = $('.tab-number', tab);
        number.innerHTML = index === state.lessonIndex ? '<span class="play-triangle"></span>' : String(index + 1);
      }
    });
    persistState();
  }

  function renderPhraseBuilder(lesson) {
    const builder = $('#phraseBuilder');
    const grid = $('#choiceGrid');
    $('.token-row', grid)?.remove();
    if (!lesson.tokens) {
      builder.hidden = true;
      return;
    }
    builder.hidden = false;
    const slots = $('#phraseSlots');
    slots.innerHTML = state.constructedPhrase.length
      ? state.constructedPhrase.map(word => `<span class="word-chip">${escapeHtml(word)}</span>`).join('')
      : '<span class="empty-phrase">点下面的词，拼成一句话</span>';
    const tokenRow = document.createElement('div');
    tokenRow.className = 'token-row';
    lesson.tokens.forEach(token => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'token-card';
      button.textContent = token;
      button.addEventListener('click', () => {
        if (state.constructedPhrase.length < lesson.tokens.length) state.constructedPhrase.push(token);
        state.lastAction = `孩子点了词卡“${token}”，目前拼出“${state.constructedPhrase.join('')}”`;
        renderLessonPhraseOnly();
        pulseContext();
      });
      tokenRow.appendChild(button);
    });
    grid.prepend(tokenRow);
  }

  function renderLesson({ announce = false } = {}) {
    const lesson = currentLesson();
    state.lastAction = `进入了“${lesson.title}”环节`;
    state.constructedPhrase = [];
    $('#lessonEyebrow').textContent = lesson.eyebrow;
    $('#lessonTitle').textContent = lesson.title;
    $('#lessonInstruction').textContent = lesson.instruction;
    $('#activityPrompt').textContent = lesson.prompt;
    $('#coachNote').textContent = lesson.coach_note;
    $('#headerLesson').textContent = lesson.title;
    $('#contextRibbon').textContent = `正在关注“${lesson.title}”`;
    $('#nextLesson span').textContent = state.lessonIndex === course.lessons.length - 1 ? '完成体验课' : '完成这一站';

    const grid = $('#choiceGrid');
    grid.innerHTML = '';
    lesson.options.forEach(option => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'choice-card';
      button.dataset.optionId = option.id;
      button.innerHTML = `<span class="choice-emoji" aria-hidden="true">${escapeHtml(option.emoji)}</span><span class="choice-label">${escapeHtml(option.label)}</span><span class="choice-caption">点一下告诉老师</span>`;
      button.setAttribute('aria-label', option.label);
      button.addEventListener('click', () => chooseOption(option, button));
      grid.appendChild(button);
    });
    renderPhraseBuilder(lesson);
    updateProgress();
    if (announce) speak(`${lesson.title}。${lesson.instruction}`);
  }

  function pulseContext() {
    $('#contextStatus').textContent = '刚刚读到学习区的新变化';
    $('#contextRibbon').textContent = state.lastAction || `正在关注“${activeContextTitle()}”`;
    window.clearTimeout(pulseContext.timer);
    pulseContext.timer = window.setTimeout(() => {
      $('#contextStatus').textContent = '已读懂右侧的学习内容';
      $('#contextRibbon').textContent = `正在关注“${activeContextTitle()}”`;
    }, 3600);
  }

  function chooseOption(option, button) {
    if (state.busy) return;
    $$('.choice-card').forEach(card => card.classList.remove('selected'));
    button.classList.add('selected');
    let expression = option.spoken;
    if (currentLesson().tokens && state.constructedPhrase.length) expression = state.constructedPhrase.join('');
    state.lastAction = `孩子在“${currentLesson().title}”中选择了“${option.label}”，表达是“${expression}”`;
    state.attempts += 1;
    updateProgress();
    pulseContext();
    speak(expression, true);
    addMessage('user', expression, { learningAction: true });
    requestTeacherResponse(expression, { alreadyRendered: true });
  }

  function addMessage(role, content, options = {}) {
    const article = document.createElement('article');
    article.className = `message ${role === 'assistant' ? 'assistant-message' : 'user-message'}`;
    if (options.learningAction) article.classList.add('learning-action');
    const bubbleHtml = `${options.learningAction ? '<span class="learning-tag">来自学习区</span>' : ''}<div class="bubble"></div>`;
    if (role === 'assistant') {
      article.innerHTML = `<div class="mini-avatar" aria-hidden="true">A</div><div>${bubbleHtml}</div>`;
    } else {
      article.innerHTML = `<div>${bubbleHtml}</div>`;
    }
    $('.bubble', article).textContent = content;
    $('#messages').appendChild(article);
    $('#messages').scrollTop = $('#messages').scrollHeight;
    if (!options.temporary) state.messages.push({ role, content });
    return article;
  }

  function addTypingMessage() {
    const article = document.createElement('article');
    article.className = 'message assistant-message';
    article.innerHTML = '<div class="mini-avatar" aria-hidden="true">A</div><div><div class="bubble typing-bubble"><i></i><i></i><i></i></div></div>';
    $('#messages').appendChild(article);
    $('#messages').scrollTop = $('#messages').scrollHeight;
    return article;
  }

  function pageContext() {
    if (state.materialMode && state.material) {
      return {
        ...(state.material.source_type === 'builtin'
          ? { builtin_id: state.material.id }
          : { material_id: state.material.id }),
        material_type: state.material.source_type,
        material_source: state.material.source_label,
        course_title: state.material.title,
        lesson_title: '自选学习材料',
        goal: '理解材料、回答问题并通过对话巩固学习',
        visible_text: String(state.material.text || '').slice(0, 12000),
        last_action: state.lastAction,
        preferences: state.preferences,
      };
    }
    const lesson = currentLesson();
    return {
      course_title: course.title,
      lesson_title: lesson.title,
      goal: lesson.goal,
      visible_text: $('#learningPanel').innerText.slice(0, 2600),
      last_action: state.lastAction,
      constructed_phrase: state.constructedPhrase.join(''),
      completed_lessons: [...state.completed],
      preferences: state.preferences,
    };
  }

  async function requestTeacherResponse(message, options = {}) {
    const text = String(message || '').trim();
    if (!text || state.busy) return;
    state.busy = true;
    $('#sendButton').disabled = true;
    if (!options.alreadyRendered) addMessage('user', text);
    const history = state.messages.slice(0, -1).slice(-16);
    const typing = addTypingMessage();
    let reply = '';
    try {
      const response = await fetch('/aiteacher/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, history, page_context: pageContext() }),
      });
      if (!response.ok || !response.body) throw new Error('课堂连接失败');
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let assistantBubble = null;
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split('\n\n');
        buffer = events.pop() || '';
        for (const event of events) {
          const line = event.split('\n').find(item => item.startsWith('data: '));
          if (!line) continue;
          const data = JSON.parse(line.slice(6));
          if (data.type === 'delta') {
            if (!assistantBubble) {
              typing.remove();
              const article = addMessage('assistant', '', { temporary: true });
              assistantBubble = $('.bubble', article);
            }
            reply += data.text;
            assistantBubble.textContent = reply;
            $('#messages').scrollTop = $('#messages').scrollHeight;
          } else if (data.type === 'error') {
            throw new Error(data.message || 'AI老师暂时没有连上');
          }
        }
      }
      if (!reply.trim()) throw new Error('AI老师暂时没有返回内容');
      state.messages.push({ role: 'assistant', content: reply.trim() });
      speak(reply.trim());
    } catch (error) {
      typing.remove();
      if (!reply) addMessage('assistant', error.message || 'AI老师暂时没有连上，请稍后再试。');
      showToast(error.message || '课堂连接失败');
    } finally {
      state.busy = false;
      $('#sendButton').disabled = false;
    }
  }

  function sendComposerMessage() {
    const input = $('#messageInput');
    const text = input.value.trim();
    if (!text || state.busy) return;
    input.value = '';
    input.style.height = '';
    state.lastAction = '孩子通过左侧对话输入了一条消息';
    requestTeacherResponse(text);
  }

  function completeLesson() {
    const lesson = currentLesson();
    state.completed.add(lesson.id);
    if (state.lessonIndex < course.lessons.length - 1) {
      state.lessonIndex += 1;
      renderLesson({ announce: true });
      $('#lessonStage').scrollTop = 0;
      showToast('很好，下一站已经准备好了');
    } else {
      updateProgress();
      showToast('体验课完成了，今天到这里也很好');
      addMessage('assistant', '今天的练习完成了。你表达了自己的选择，这很重要。现在可以休息。');
      speak('今天的练习完成了。你表达了自己的选择，这很重要。现在可以休息。');
    }
  }

  function startWaitTimer() {
    if (waitTimer) return;
    const button = $('#waitButton');
    let seconds = 5;
    button.classList.add('counting');
    $('#waitLabel').textContent = `安静等待 ${seconds}`;
    waitTimer = window.setInterval(() => {
      seconds -= 1;
      $('#waitLabel').textContent = seconds > 0 ? `安静等待 ${seconds}` : '谢谢你愿意等';
      if (seconds <= 0) {
        window.clearInterval(waitTimer);
        waitTimer = null;
        window.setTimeout(() => {
          button.classList.remove('counting');
          $('#waitLabel').textContent = '留出 5 秒';
        }, 1200);
      }
    }, 1000);
  }

  async function startRecording() {
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      showToast('当前浏览器不支持录音，请使用文字输入');
      return;
    }
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const preferred = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4'].find(type => MediaRecorder.isTypeSupported(type));
      mediaRecorder = preferred ? new MediaRecorder(mediaStream, { mimeType: preferred }) : new MediaRecorder(mediaStream);
      audioChunks = [];
      mediaRecorder.addEventListener('dataavailable', event => { if (event.data.size) audioChunks.push(event.data); });
      mediaRecorder.addEventListener('stop', uploadRecording, { once: true });
      mediaRecorder.start();
      recordStartedAt = Date.now();
      $('#recordingState').hidden = false;
      recordTimer = window.setInterval(updateRecordingTime, 250);
      updateRecordingTime();
      window.setTimeout(() => { if (mediaRecorder?.state === 'recording') stopRecording(); }, 30000);
    } catch (_) {
      showToast('没有取得麦克风权限，可以继续打字');
    }
  }

  function updateRecordingTime() {
    const seconds = Math.floor((Date.now() - recordStartedAt) / 1000);
    $('#recordingTime').textContent = `00:${String(seconds).padStart(2, '0')}`;
  }

  function stopRecording() {
    if (mediaRecorder?.state === 'recording') mediaRecorder.stop();
    window.clearInterval(recordTimer);
    $('#recordingState').hidden = true;
    mediaStream?.getTracks().forEach(track => track.stop());
  }

  async function uploadRecording() {
    if (!audioChunks.length) return;
    const mime = mediaRecorder?.mimeType || 'audio/webm';
    const ext = mime.includes('mp4') ? 'm4a' : mime.includes('ogg') ? 'ogg' : 'webm';
    const form = new FormData();
    form.append('audio', new Blob(audioChunks, { type: mime }), `speech.${ext}`);
    showToast('正在听懂你说的话…');
    try {
      const response = await fetch('/aiteacher/api/asr', { method: 'POST', body: form });
      const result = await response.json();
      if (!response.ok || !result.success) throw new Error(result.error || '语音识别失败');
      $('#messageInput').value = result.text;
      state.lastAction = '孩子用语音说了一句话';
      sendComposerMessage();
    } catch (error) {
      showToast(error.message || '没有听清，请再说一次');
    }
  }

  function openProfile() {
    $('#learnerName').value = state.preferences.name || '';
    $('#learnerInterests').value = state.preferences.interests || '';
    $('#speechRate').value = String(state.preferences.speechRate || 0.86);
    $$('input[name="mode"]').forEach(box => { box.checked = state.preferences.modes.includes(box.value); });
    $('#profileDialog').showModal();
  }

  function saveProfile(event) {
    if (event.submitter?.value === 'cancel') return;
    event.preventDefault();
    state.preferences = {
      name: $('#learnerName').value.trim(),
      modes: $$('input[name="mode"]:checked').map(box => box.value),
      interests: $('#learnerInterests').value.trim(),
      speechRate: Number($('#speechRate').value),
    };
    persistState();
    $('#profileDialog').close();
    showToast('学习偏好已保存');
  }

  const materialTypeNames = {
    builtin: '系统教程',
    generated: 'AI 生成课件',
    url: '网页材料',
    upload: '上传材料',
  };

  const materialTypeShortNames = {
    builtin: '系统',
    generated: 'AI',
    url: '网页',
    upload: '文件',
  };

  function setMaterialMode(mode) {
    $$('.material-mode-tabs [data-material-mode]').forEach(button => {
      button.classList.toggle('active', button.dataset.materialMode === mode);
    });
    $$('[data-material-panel]').forEach(panel => {
      panel.hidden = panel.dataset.materialPanel !== mode;
    });
    $('#materialFormError').hidden = true;
    if (mode === 'system') loadBuiltinMaterials();
    if (mode === 'saved') loadSavedMaterials();
  }

  function openMaterialDialog(mode = 'system') {
    setMaterialMode(mode);
    if (!$('#materialDialog').open) $('#materialDialog').showModal();
  }

  function setMaterialFormBusy(form, busy, waitingText) {
    const button = $('.material-submit', form);
    const label = $('span', button);
    if (!button.dataset.defaultLabel) button.dataset.defaultLabel = label.textContent;
    button.disabled = busy;
    label.textContent = busy ? waitingText : button.dataset.defaultLabel;
  }

  async function responseJson(response) {
    let result = {};
    try { result = await response.json(); } catch (_) { /* handled below */ }
    if (!response.ok || !result.success) {
      throw new Error(result.error || '学习材料处理失败');
    }
    return result;
  }

  function renderBuiltinMaterials(materials) {
    const list = $('#builtinMaterialList');
    list.innerHTML = '';
    if (!materials.length) {
      list.innerHTML = '<p class="saved-material-empty">暂时没有可用的系统教程。</p>';
      return;
    }
    materials.forEach(material => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'saved-material-item';
      button.dataset.builtinId = material.id;
      const kind = document.createElement('span');
      kind.className = 'saved-material-kind';
      kind.textContent = '系统';
      const copy = document.createElement('span');
      copy.className = 'saved-material-copy';
      const title = document.createElement('strong');
      title.textContent = material.title;
      const meta = document.createElement('small');
      meta.textContent = `${material.subtitle || '系统教程'}${material.duration ? ` · ${material.duration}` : ''} · ${material.description || ''}`;
      const action = document.createElement('span');
      action.className = 'saved-material-open';
      action.textContent = '开始学习 →';
      copy.append(title, meta);
      button.append(kind, copy, action);
      list.appendChild(button);
    });
  }

  async function loadBuiltinMaterials() {
    const list = $('#builtinMaterialList');
    list.innerHTML = '<p class="saved-material-empty">正在读取系统教程…</p>';
    try {
      const response = await fetch('/aiteacher/api/builtin-materials');
      const result = await responseJson(response);
      renderBuiltinMaterials(result.materials || []);
    } catch (error) {
      list.innerHTML = '';
      const empty = document.createElement('p');
      empty.className = 'saved-material-empty';
      empty.textContent = error.message;
      list.appendChild(empty);
    }
  }

  async function openBuiltinMaterial(materialId, options = {}) {
    try {
      const response = await fetch(`/aiteacher/api/builtin-materials/${encodeURIComponent(materialId)}`);
      const result = await responseJson(response);
      if ($('#materialDialog').open) $('#materialDialog').close();
      showMaterial(result.material, options);
      if (!options.silent) showToast('已打开系统教程');
    } catch (error) {
      $('#materialFormError').textContent = error.message;
      $('#materialFormError').hidden = false;
      if (options.silent) showToast('系统教程暂时无法打开');
    }
  }

  function renderSavedMaterials(materials) {
    const list = $('#savedMaterialList');
    list.innerHTML = '';
    if (!materials.length) {
      list.innerHTML = '<p class="saved-material-empty">还没有已保存的材料。生成、导入或上传后会出现在这里。</p>';
      return;
    }
    materials.forEach(material => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'saved-material-item';
      button.dataset.materialId = material.id;

      const kind = document.createElement('span');
      kind.className = 'saved-material-kind';
      kind.textContent = materialTypeShortNames[material.source_type] || '材料';
      const copy = document.createElement('span');
      copy.className = 'saved-material-copy';
      const title = document.createElement('strong');
      title.textContent = material.title || '未命名学习材料';
      const meta = document.createElement('small');
      const created = material.created_at ? new Date(material.created_at).toLocaleString('zh-CN', { hour12: false }) : '';
      meta.textContent = `${materialTypeNames[material.source_type] || '学习材料'}${created ? ` · ${created}` : ''}`;
      const action = document.createElement('span');
      action.className = 'saved-material-open';
      action.textContent = '打开 →';
      copy.append(title, meta);
      button.append(kind, copy, action);
      list.appendChild(button);
    });
  }

  async function loadSavedMaterials() {
    const list = $('#savedMaterialList');
    list.innerHTML = '<p class="saved-material-empty">正在读取已保存材料…</p>';
    try {
      const response = await fetch('/aiteacher/api/materials');
      const result = await responseJson(response);
      const paths = result.storage_paths?.length ? result.storage_paths : [result.storage_path];
      $('#materialStoragePath').textContent = `保存位置：${paths.filter(Boolean).join('；')}`;
      renderSavedMaterials(result.materials || []);
    } catch (error) {
      list.innerHTML = '';
      const empty = document.createElement('p');
      empty.className = 'saved-material-empty';
      empty.textContent = error.message;
      list.appendChild(empty);
    }
  }

  async function openSavedMaterial(materialId) {
    if (!materialId) return;
    try {
      const response = await fetch(`/aiteacher/api/materials/${encodeURIComponent(materialId)}`);
      const result = await responseJson(response);
      $('#materialDialog').close();
      showMaterial(result.material);
      showToast('已打开保存的学习材料');
    } catch (error) {
      $('#materialFormError').textContent = error.message;
      $('#materialFormError').hidden = false;
    }
  }

  function showMaterial(material, options = {}) {
    state.material = material;
    state.materialMode = true;
    $('#lessonTabs').hidden = true;
    $('#lessonStage').hidden = true;
    $('.lesson-footer').hidden = true;
    $('.course-progress-wrap').hidden = true;
    $('#materialViewer').hidden = false;
    $('#courseSourceLabel').textContent = materialTypeNames[material.source_type] || '学习材料';
    $('#courseMetaLabel').textContent = material.duration || 'AI老师已读取';
    $('#courseTitle').textContent = material.title;
    $('#headerLesson').textContent = material.title;
    $('#materialTypeBadge').textContent = materialTypeNames[material.source_type] || '学习材料';
    $('#materialSourceText').textContent = material.source_label || '正文已准备好，可以开始提问';
    $('#materialFrameLoading').hidden = false;
    $('#materialFrame').src = `${material.viewer_url}?v=${Date.now()}`;
    state.lastAction = `打开了学习材料“${material.title}”`;
    pulseContext();
    if (!options.silent) {
      addMessage('assistant', `我已经读过“${material.title}”。你可以直接问我问题，也可以让我从头讲起。`);
      speak(`学习材料已经打开。你可以问我问题。`);
    }
  }

  function openDefaultBuiltin() {
    return openBuiltinMaterial('functional-communication-starter', { silent: true });
  }

  async function submitGeneratedMaterial(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const requirement = $('#materialRequirement').value.trim();
    if (!requirement) return;
    setMaterialFormBusy(form, true, 'AI 正在设计课件…');
    $('#materialFormError').hidden = true;
    try {
      const response = await fetch('/aiteacher/api/material/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ requirement }),
      });
      const result = await responseJson(response);
      $('#materialDialog').close();
      showMaterial(result.material);
      showToast('教学网页已生成并保存');
    } catch (error) {
      $('#materialFormError').textContent = error.message;
      $('#materialFormError').hidden = false;
    } finally {
      setMaterialFormBusy(form, false, '');
    }
  }

  async function submitUrlMaterial(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const url = $('#materialUrl').value.trim();
    if (!url) return;
    setMaterialFormBusy(form, true, '正在读取网页…');
    $('#materialFormError').hidden = true;
    try {
      const response = await fetch('/aiteacher/api/material/url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      });
      const result = await responseJson(response);
      $('#materialDialog').close();
      showMaterial(result.material);
      showToast('网页已读取并保存为学习材料');
    } catch (error) {
      $('#materialFormError').textContent = error.message;
      $('#materialFormError').hidden = false;
    } finally {
      setMaterialFormBusy(form, false, '');
    }
  }

  async function submitUploadedMaterial(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const file = $('#materialFile').files[0];
    if (!file) return;
    const body = new FormData();
    body.append('file', file);
    setMaterialFormBusy(form, true, '正在上传并读取…');
    $('#materialFormError').hidden = true;
    try {
      const response = await fetch('/aiteacher/api/material/upload', { method: 'POST', body });
      const result = await responseJson(response);
      $('#materialDialog').close();
      showMaterial(result.material);
      showToast('文件已保存为学习材料');
    } catch (error) {
      $('#materialFormError').textContent = error.message;
      $('#materialFormError').hidden = false;
    } finally {
      setMaterialFormBusy(form, false, '');
    }
  }

  function accountInitial(username) {
    return String(username || '访').trim().slice(0, 1).toUpperCase() || '访';
  }

  function renderAccount() {
    const loggedIn = state.account.isLoggedIn && state.account.user;
    const user = state.account.user || {};
    const initial = accountInitial(user.username);
    $('#accountAvatar').textContent = initial;
    $('#accountName').textContent = loggedIn ? user.username : '登录 / 注册';
    $('#accountSummary').hidden = !loggedIn;
    $('#accountLoginAction').hidden = Boolean(loggedIn);
    $('#accountRegisterAction').hidden = Boolean(loggedIn);
    $('#accountProfileAction').hidden = !loggedIn;
    $('#accountPreferencesAction').hidden = !loggedIn;
    $('#accountLogoutAction').hidden = !loggedIn;
    if (loggedIn) {
      $('#accountSummaryAvatar').textContent = initial;
      $('#accountSummaryName').textContent = user.username;
      $('#accountSummaryEmail').textContent = user.email || '已登录';
    }
  }

  async function accountRequest(url, options = {}) {
    const response = await fetch(url, {
      credentials: 'same-origin',
      ...options,
      headers: options.body ? { 'Content-Type': 'application/json', ...(options.headers || {}) } : options.headers,
    });
    let result = {};
    try { result = await response.json(); } catch (_) { /* handled below */ }
    if (!response.ok || result.status !== 'success') throw new Error(result.message || '账号操作失败，请稍后重试');
    return result;
  }

  async function refreshAccount() {
    try {
      const result = await accountRequest('/account/api/check_login');
      state.account = { isLoggedIn: Boolean(result.isLoggedIn), user: result.user || null };
    } catch (_) {
      state.account = { isLoggedIn: false, user: null };
    }
    renderAccount();
  }

  function closeAccountMenu() {
    $('#accountMenu').hidden = true;
    $('#accountTrigger').setAttribute('aria-expanded', 'false');
  }

  function toggleAccountMenu() {
    const willOpen = $('#accountMenu').hidden;
    $('#accountMenu').hidden = !willOpen;
    $('#accountTrigger').setAttribute('aria-expanded', String(willOpen));
  }

  function setAccountMode(mode) {
    $$('.account-tabs [data-account-mode]').forEach(button => {
      button.classList.toggle('active', button.dataset.accountMode === mode);
    });
    $$('[data-account-panel]').forEach(panel => { panel.hidden = panel.dataset.accountPanel !== mode; });
    $('#accountDialogTitle').textContent = mode === 'register' ? '创建学习账号' : '登录账号';
    $('#accountFormError').hidden = true;
  }

  function openAccountDialog(mode) {
    closeAccountMenu();
    setAccountMode(mode);
    if (mode === 'login') {
      try {
        const remembered = localStorage.getItem('aiteacher-remembered-account') || '';
        if (!$('#loginAccount').value) $('#loginAccount').value = remembered;
        $('#rememberAccount').checked = Boolean(remembered);
      } catch (_) { /* Remembering an account is optional. */ }
    }
    if (!$('#accountDialog').open) $('#accountDialog').showModal();
    window.setTimeout(() => $(mode === 'register' ? '#registerUsername' : '#loginAccount').focus(), 0);
  }

  function setAccountFormBusy(form, busy, waitingText) {
    const button = $('.account-submit', form);
    const label = $('span', button);
    if (!button.dataset.defaultLabel) button.dataset.defaultLabel = label.textContent;
    button.disabled = busy;
    label.textContent = busy ? waitingText : button.dataset.defaultLabel;
  }

  function showAccountError(message) {
    $('#accountFormError').textContent = message;
    $('#accountFormError').hidden = false;
  }

  async function submitLogin(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const account = $('#loginAccount').value.trim();
    const password = $('#loginPassword').value;
    setAccountFormBusy(form, true, '正在登录…');
    $('#accountFormError').hidden = true;
    try {
      const result = await accountRequest('/account/api/login', {
        method: 'POST', body: JSON.stringify({ username: account, password }),
      });
      state.account = { isLoggedIn: true, user: result.user };
      try {
        if ($('#rememberAccount').checked) localStorage.setItem('aiteacher-remembered-account', account);
        else localStorage.removeItem('aiteacher-remembered-account');
      } catch (_) { /* Login must not depend on browser storage. */ }
      renderAccount();
      $('#accountDialog').close();
      form.reset();
      showToast(`欢迎回来，${result.user.username}`);
    } catch (error) {
      showAccountError(error.message);
    } finally {
      setAccountFormBusy(form, false, '');
    }
  }

  async function submitRegister(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const username = $('#registerUsername').value.trim();
    const email = $('#registerEmail').value.trim();
    const password = $('#registerPassword').value;
    if (password !== $('#registerPasswordConfirm').value) {
      showAccountError('两次输入的密码不一致');
      return;
    }
    setAccountFormBusy(form, true, '正在创建账号…');
    $('#accountFormError').hidden = true;
    try {
      await accountRequest('/account/api/register', {
        method: 'POST', body: JSON.stringify({ username, email, password }),
      });
      const result = await accountRequest('/account/api/login', {
        method: 'POST', body: JSON.stringify({ username, password }),
      });
      state.account = { isLoggedIn: true, user: result.user };
      renderAccount();
      $('#accountDialog').close();
      form.reset();
      showToast(`账号创建成功，欢迎你，${username}`);
    } catch (error) {
      showAccountError(error.message);
    } finally {
      setAccountFormBusy(form, false, '');
    }
  }

  async function showAccountProfile() {
    closeAccountMenu();
    try {
      const result = await accountRequest('/account/api/profile');
      const profile = result.data;
      $('#accountInfoAvatar').textContent = accountInitial(profile.username);
      $('#accountInfoName').textContent = profile.username || '—';
      $('#accountInfoEmail').textContent = profile.email || '—';
      $('#accountInfoId').textContent = profile.user_id || '—';
      $('#accountInfoRegistered').textContent = profile.register_time || '暂无记录';
      $('#accountInfoDialog').showModal();
    } catch (error) {
      showToast(error.message);
    }
  }

  async function logoutAccount() {
    closeAccountMenu();
    try {
      await accountRequest('/account/api/logout');
      state.account = { isLoggedIn: false, user: null };
      renderAccount();
      showToast('已安全退出账号');
    } catch (error) {
      showToast(error.message);
    }
  }

  function bindEvents() {
    $('#sendButton').addEventListener('click', sendComposerMessage);
    $('#messageInput').addEventListener('keydown', event => {
      if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); sendComposerMessage(); }
    });
    $('#messageInput').addEventListener('input', event => {
      event.target.style.height = 'auto';
      event.target.style.height = `${Math.min(event.target.scrollHeight, 100)}px`;
    });
    $('#starterPrompts').addEventListener('click', event => {
      const prompt = event.target.closest('[data-prompt]');
      if (prompt) requestTeacherResponse(prompt.dataset.prompt);
    });
    $('#messages').addEventListener('click', event => {
      const replay = event.target.closest('[data-speak]');
      if (replay) speak(replay.dataset.speak, true);
    });
    $('#listenPrompt').addEventListener('click', () => speak(`${currentLesson().prompt} ${currentLesson().instruction}`, true));
    $('#waitButton').addEventListener('click', startWaitTimer);
    $('#nextLesson').addEventListener('click', completeLesson);
    $('#clearPhrase').addEventListener('click', () => { state.constructedPhrase = []; renderLessonPhraseOnly(true); });
    $$('.lesson-tab').forEach(tab => tab.addEventListener('click', () => {
      state.lessonIndex = Number(tab.dataset.lessonIndex);
      renderLesson({ announce: false });
    }));
    $('#voiceOutputToggle').addEventListener('click', event => {
      state.autoVoice = !state.autoVoice;
      event.currentTarget.setAttribute('aria-pressed', String(state.autoVoice));
      if (!state.autoVoice) window.speechSynthesis?.cancel();
      persistState();
      showToast(state.autoVoice ? '老师语音已开启' : '老师语音已关闭');
    });
    $('#quietToggle').addEventListener('click', event => {
      state.quiet = !state.quiet;
      document.body.classList.toggle('quiet-mode', state.quiet);
      event.currentTarget.setAttribute('aria-pressed', String(state.quiet));
      if (state.quiet) window.speechSynthesis?.cancel();
      persistState();
      showToast(state.quiet ? '已减少动画和声音' : '已退出安静模式');
    });
    $('#micButton').addEventListener('click', startRecording);
    $('#stopRecording').addEventListener('click', stopRecording);
    $('#profileOpen').addEventListener('click', openProfile);
    $('#profileForm').addEventListener('submit', saveProfile);
    $('#accountTrigger').addEventListener('click', toggleAccountMenu);
    $('#accountLoginAction').addEventListener('click', () => openAccountDialog('login'));
    $('#accountRegisterAction').addEventListener('click', () => openAccountDialog('register'));
    $('#accountProfileAction').addEventListener('click', showAccountProfile);
    $('#accountPreferencesAction').addEventListener('click', () => { closeAccountMenu(); openProfile(); });
    $('#accountLogoutAction').addEventListener('click', logoutAccount);
    $('#accountDialogClose').addEventListener('click', () => $('#accountDialog').close());
    $('#accountInfoClose').addEventListener('click', () => $('#accountInfoDialog').close());
    $('#accountInfoPreferences').addEventListener('click', () => { $('#accountInfoDialog').close(); openProfile(); });
    $$('.account-tabs [data-account-mode]').forEach(button => button.addEventListener('click', () => setAccountMode(button.dataset.accountMode)));
    $('#loginForm').addEventListener('submit', submitLogin);
    $('#registerForm').addEventListener('submit', submitRegister);
    document.addEventListener('click', event => {
      if (!$('#accountControl').contains(event.target)) closeAccountMenu();
    });
    document.addEventListener('keydown', event => { if (event.key === 'Escape') closeAccountMenu(); });
    $('#materialOpen').addEventListener('click', () => openMaterialDialog('system'));
    $('#replaceMaterial').addEventListener('click', () => openMaterialDialog('system'));
    $('#materialClose').addEventListener('click', () => $('#materialDialog').close());
    $$('.material-mode-tabs [data-material-mode]').forEach(button => {
      button.addEventListener('click', () => setMaterialMode(button.dataset.materialMode));
    });
    $('#generateMaterialForm').addEventListener('submit', submitGeneratedMaterial);
    $('#urlMaterialForm').addEventListener('submit', submitUrlMaterial);
    $('#uploadMaterialForm').addEventListener('submit', submitUploadedMaterial);
    $('#materialFile').addEventListener('change', event => {
      const file = event.target.files[0];
      $('#uploadFileLabel').textContent = file ? file.name : '选择 HTML、Markdown 或 TXT 文件';
    });
    $('#refreshSavedMaterials').addEventListener('click', loadSavedMaterials);
    $('#refreshBuiltinMaterials').addEventListener('click', loadBuiltinMaterials);
    $('#builtinMaterialList').addEventListener('click', event => {
      const item = event.target.closest('[data-builtin-id]');
      if (item) openBuiltinMaterial(item.dataset.builtinId);
    });
    $('#savedMaterialList').addEventListener('click', event => {
      const item = event.target.closest('[data-material-id]');
      if (item) openSavedMaterial(item.dataset.materialId);
    });
    $('#materialFrame').addEventListener('load', () => { $('#materialFrameLoading').hidden = true; });
    window.addEventListener('message', event => {
      if (event.source !== $('#materialFrame').contentWindow || !state.material) return;
      const payload = event.data || {};
      if (payload.type !== 'aiteacher-learning-action') return;
      const action = String(payload.action || '').slice(0, 300);
      const spoken = String(payload.spoken || '').slice(0, 300);
      if (action) {
        state.lastAction = action;
        pulseContext();
      }
      if (spoken) {
        speak(spoken, true);
        if (payload.respond) {
          state.attempts += 1;
          addMessage('user', spoken, { learningAction: true });
          requestTeacherResponse(spoken, { alreadyRendered: true });
        }
      }
    });
  }

  function renderLessonPhraseOnly(wasCleared = false) {
    const lesson = currentLesson();
    const slots = $('#phraseSlots');
    slots.innerHTML = state.constructedPhrase.length
      ? state.constructedPhrase.map(word => `<span class="word-chip">${escapeHtml(word)}</span>`).join('')
      : '<span class="empty-phrase">点下面的词，拼成一句话</span>';
    if (wasCleared) {
      state.lastAction = '孩子清空了刚才拼的词，准备重新表达';
      pulseContext();
    }
  }

  restoreState();
  document.body.classList.toggle('quiet-mode', state.quiet);
  $('#quietToggle').setAttribute('aria-pressed', String(state.quiet));
  $('#voiceOutputToggle').setAttribute('aria-pressed', String(state.autoVoice));
  bindEvents();
  renderLesson();
  refreshAccount();
  openDefaultBuiltin();
})();
