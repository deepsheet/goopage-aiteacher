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
    autoSpeakReplies: true,
    // 音色代码；留空表示跟随服务端下发的默认音色（当前的 VoxCPM2 真人声）。
    voice: '',
    proactiveWait: false,
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

  // 云端语音合成播放控制：用 Web Audio 播放以规避自动播放策略；
  // speakToken 用于“新语音抢占旧语音”，activeSources 便于随时停止。
  let audioCtx = null;
  let activeSources = [];
  let speakToken = 0;
  let pendingSpeech = '';

  function restoreState() {
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey) || '{}');
      state.lessonIndex = Math.max(0, Math.min(course.lessons.length - 1, Number(saved.lessonIndex) || 0));
      state.completed = new Set(Array.isArray(saved.completed) ? saved.completed : []);
      state.attempts = Number(saved.attempts) || 0;
      state.autoVoice = saved.autoVoice !== false;
      state.autoSpeakReplies = saved.autoSpeakReplies !== false;
      if (saved.voice) state.voice = saved.voice;
      state.proactiveWait = saved.proactiveWait === true;
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
        autoSpeakReplies: state.autoSpeakReplies,
        voice: state.voice,
        proactiveWait: state.proactiveWait,
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

  function stopSpeaking() {
    speakToken += 1;
    activeSources.forEach(source => { try { source.stop(0); } catch (_) { /* 已停止 */ } });
    activeSources = [];
    if (window.speechSynthesis) window.speechSynthesis.cancel();
  }

  function speechPlaybackRate() {
    const rate = Number(state.preferences.speechRate) || 1;
    return Math.min(1.25, Math.max(0.75, rate));
  }

  // 浏览器自带合成作为兜底（云端不可用时）。
  function speakBrowser(text) {
    if (!('speechSynthesis' in window) || !text) return;
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

  function ensureAudioContext() {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return null;
    if (!audioCtx) audioCtx = new Ctx();
    if (audioCtx.state === 'suspended') audioCtx.resume().catch(() => {});
    return audioCtx;
  }

  // 在一个用户手势里调用，提前“解锁”AudioContext；
  // 之后即便在流式回复的异步回调里播放，也不再受自动播放策略限制。
  function unlockAudio() {
    const ctx = ensureAudioContext();
    if (!ctx) return;
    const buffer = ctx.createBuffer(1, 1, ctx.sampleRate);
    const source = ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(ctx.destination);
    source.start(0);
  }

  // AudioContext 只有在真实用户手势后才能进入 running；
  // 课件 iframe 里的点击不会传递到父文档，所以可能永远停在 suspended。
  // 无手势时 resume() 会一直挂起，用短超时兑底，避免 speak 卡死。
  async function audioReady() {
    const ctx = ensureAudioContext();
    if (!ctx) return false;
    if (ctx.state === 'running') return true;
    await Promise.race([
      ctx.resume().catch(() => {}),
      new Promise(resolve => window.setTimeout(resolve, 500)),
    ]);
    return ctx.state === 'running';
  }

  function base64ToAudioBuffer(dataUri) {
    const ctx = ensureAudioContext();
    if (!ctx) return Promise.resolve(null);
    const b64 = String(dataUri).split(',', 2)[1] || '';
    const binary = window.atob(b64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
    return ctx.decodeAudioData(bytes.buffer).catch(() => null);
  }

  function playBuffer(buffer, token) {
    return new Promise(resolve => {
      const ctx = audioCtx;
      if (!buffer || !ctx || token !== speakToken) { resolve(); return; }
      const source = ctx.createBufferSource();
      source.buffer = buffer;
      source.playbackRate.value = speechPlaybackRate();
      source.connect(ctx.destination);
      activeSources.push(source);
      let settled = false;
      const finish = () => {
        if (settled) return;
        settled = true;
        activeSources = activeSources.filter(item => item !== source);
        resolve();
      };
      source.onended = finish;
      try { source.start(0); } catch (_) { finish(); }
    });
  }

  async function speak(text, force = false) {
    const clean = extractHighlightDirectives(String(text || '').replace(/[*#`]/g, '')).text.trim();
    if ((!state.autoVoice && !force) || !clean) return;
    stopSpeaking();
    const token = speakToken;
    try {
      if (!ensureAudioContext()) { speakBrowser(clean); return; }
      if (!(await audioReady())) {
        // 浏览器自动播放策略锁住了声音：记住这句，引导用户点一下开启。
        pendingSpeech = clean;
        showVoiceBanner();
        return;
      }
      hideVoiceBanner();
      // 记住这次到底要哪个音色：服务端可能因为不可用/代码不认识而换成另一个，
      // 只要实际出声的不是它，就得告诉用户，不能让人以为是自己选错了。
      const requestedVoice = state.voice;
      const response = await fetch('/aiteacher/api/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: clean, voice: requestedVoice }),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok || !result.success || !Array.isArray(result.clips) || !result.clips.length) {
        throw new Error(result.error || '语音合成失败');
      }
      // 服务端在首选音色不可用时只能拿另一个音色兜底，那等于换了个人说话；
      // 不能静默，否则用户会以为是自己选错了音色。
      if (token === speakToken && result.voice && result.voice !== requestedVoice) {
        showToast(`“${voiceName(requestedVoice)}”这一句没连上，先用了“${voiceName(result.voice)}”`);
      }
      for (const clip of result.clips) {
        if (token !== speakToken) return; // 已被更新的语音取代
        const buffer = await base64ToAudioBuffer(clip);
        if (token !== speakToken) return;
        await playBuffer(buffer, token);
      }
    } catch (error) {
      // 云端不可用时回退到浏览器合成，保证老师仍能发声。
      // 但设备自带音色和老师音色不是一个人，静默切换会被当成故障，必须说一声。
      if (token === speakToken) {
        showToast('语音服务没响应，这一句改用了设备自带发音');
        speakBrowser(clean);
      }
    }
  }

  function updateVoiceToggle() {
    const button = $('#voiceOutputToggle');
    if (!button) return;
    button.setAttribute('aria-pressed', String(state.autoVoice));
    const label = state.autoVoice ? '老师语音已开启（点击关闭）' : '老师语音已关闭（点击开启）';
    button.title = label;
    button.setAttribute('aria-label', label);
  }

  // 音色选择：音色列表由服务端下发，选择结果持久化到 localStorage。
  let voiceOptions = [];

  function voiceName(code) {
    const found = voiceOptions.find(option => option.code === code);
    return found ? (found.name || code) : (code || '老师');
  }

  function currentVoiceName() {
    const found = voiceOptions.find(option => option.code === state.voice);
    return found ? found.name : '';
  }

  function updateTimbreButton() {
    const button = $('#voiceTimbreToggle');
    if (!button) return;
    const name = currentVoiceName();
    const label = name ? `选择老师的声音（当前：${name}）` : '选择老师的声音';
    button.title = label;
    button.setAttribute('aria-label', label);
  }

  function renderVoiceTimbreMenu() {
    const list = $('#voiceTimbreList');
    if (!list) return;
    list.innerHTML = '';
    voiceOptions.forEach(option => {
      const item = document.createElement('button');
      item.type = 'button';
      item.className = 'voice-timbre-item';
      item.setAttribute('role', 'menuitemradio');
      item.dataset.voice = option.code;
      item.setAttribute('aria-checked', String(option.code === state.voice));

      const nameRow = document.createElement('span');
      nameRow.className = 'vt-name';
      const nameText = document.createElement('span');
      nameText.textContent = option.name || option.code;
      const gender = document.createElement('span');
      gender.className = 'vt-gender';
      gender.textContent = option.gender || '';
      nameRow.append(nameText, gender);

      const desc = document.createElement('span');
      desc.className = 'vt-desc';
      // 真人音色的说话人实际锁不住（每条都可能换个人的声音），先写清楚再让用户选。
      desc.textContent = option.unstable
        ? `${option.desc || ''} · 每条会有点不一样`
        : (option.desc || '');

      item.append(nameRow, desc);
      item.addEventListener('click', () => selectVoice(option.code));
      list.appendChild(item);
    });
  }

  function selectVoice(code) {
    if (!code || code === state.voice) { closeTimbreMenu(); return; }
    state.voice = code;
    persistState();
    updateTimbreButton();
    $$('#voiceTimbreList .voice-timbre-item').forEach(item => {
      item.setAttribute('aria-checked', String(item.dataset.voice === code));
    });
    closeTimbreMenu();
    const name = currentVoiceName();
    const chosen = voiceOptions.find(option => option.code === code) || {};
    showToast(chosen.unstable
      ? `老师的声音已换成“${name}”（真人音色会有点即兴，每条不完全是同一个声音）`
      : `老师的声音已换成“${name}”`);
    // 用一句短提示试听新音色（force=true 忽略当前开关）。
    speak(`你好，我是${name}，我们慢慢来。`, true);
  }

  function toggleTimbreMenu(forceOpen) {
    const menu = $('#voiceTimbreMenu');
    const button = $('#voiceTimbreToggle');
    if (!menu || !button) return;
    const willOpen = typeof forceOpen === 'boolean' ? forceOpen : menu.hidden;
    menu.hidden = !willOpen;
    button.setAttribute('aria-expanded', String(willOpen));
  }

  function closeTimbreMenu() { toggleTimbreMenu(false); }

  async function loadVoiceOptions() {
    try {
      const response = await fetch('/aiteacher/api/tts/voices');
      const result = await response.json().catch(() => ({}));
      if (!response.ok || !result.success || !Array.isArray(result.voices)) return;
      voiceOptions = result.voices;
      if (!voiceOptions.some(option => option.code === state.voice)) {
        state.voice = result.default || voiceOptions[0]?.code || state.voice;
      }
      renderVoiceTimbreMenu();
      updateTimbreButton();
    } catch (_) { /* 拉取失败时保留默认音色，不影响正常发音。 */ }
  }

  function showVoiceBanner() {
    const banner = $('#voiceBanner');
    if (banner) banner.hidden = false;
  }

  function hideVoiceBanner() {
    const banner = $('#voiceBanner');
    if (banner) banner.hidden = true;
    pendingSpeech = '';
  }

  function currentLesson() { return course.lessons[state.lessonIndex]; }

  function contextNoun() {
    return state.materialMode && state.material ? '这份课件' : '当前环节';
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
        observeActivity();
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
    $('#contextRibbon').textContent = '正在关注当前环节';
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
    if (announce) {
      // 老师把环节说完后，才进入“观察沉默”的等待窗口。
      speak(`${lesson.title}。${lesson.instruction}`).then(() => beginExpecting());
    } else {
      beginExpecting();
    }
  }

  function pulseContext() {
    $('#contextRibbon').textContent = state.lastAction || `正在关注${contextNoun()}`;
    window.clearTimeout(pulseContext.timer);
    pulseContext.timer = window.setTimeout(() => {
      $('#contextRibbon').textContent = `正在关注${contextNoun()}`;
    }, 3600);
  }

  function chooseOption(option, button) {
    if (state.busy) return;
    observeActivity();
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

  // AI 回复里嵌入的课件控制指令：[[highlight:课件原文]] 高亮定位，
  // [[hint:单词]] / [[reveal:单词]] / [[step:序号]] 操作练习区。
  // 均不显示给学员，前端剥离后转发给课件 iframe。
  const DIRECTIVE_RE = /\[\[\s*(highlight|hint|reveal|step)\s*[:：]\s*([^\[\]\n]{1,100}?)\s*\]\]/gi;
  const DIRECTIVE_TYPES = ['highlight', 'hint', 'reveal', 'step'];

  function extractHighlightDirectives(raw) {
    const queries = [];
    const commands = [];
    const text = String(raw || '').replace(DIRECTIVE_RE, (_, type, value) => {
      const item = value.trim();
      if (item) {
        if (String(type).toLowerCase() === 'highlight') queries.push(item);
        else commands.push({ type: String(type).toLowerCase(), value: item });
      }
      return '';
    });
    // 流式回复指令是逐字到达的：上面移除的都是已闭合的，剩下的 `[[` 开头就是半截指令。
    // 只暂扣“还可能长成已知指令”的开头（[[h / [[hint:ha），不要求前缀已经打完，
    // 否则标记前几个字符会先闪现在气泡里；不像指令的 `[[` 归回正文。
    const lower = text.toLowerCase();
    let openIdx = -1;
    let cursor = text.indexOf('[[');
    while (cursor !== -1) {
      const fragment = lower.slice(cursor);
      const candidate = DIRECTIVE_TYPES.some(prefix => {
        const opener = `[[${prefix}`;
        return opener.startsWith(fragment) || fragment.startsWith(opener);
      });
      if (candidate && !fragment.includes(']]')) {
        openIdx = cursor;   // 从左往右扫，第一个就是最早的
        break;
      }
      cursor = text.indexOf('[[', cursor + 2);
    }
    if (openIdx !== -1 && text.slice(openIdx).length <= 300) {
      return { text: text.slice(0, openIdx), queries, commands };
    }
    return { text, queries, commands };
  }

  // 只有右侧确实正在展示课件时才能收到指令，否则 postMessage 会发给空 iframe。
  function activeMaterialFrame() {
    if (!state.materialMode || !state.material) return null;
    const frame = $('#materialFrame');
    const viewer = $('#materialViewer');
    if (!frame || !viewer || viewer.hidden) return null;
    return frame;
  }

  function highlightInMaterial(query) {
    const frame = activeMaterialFrame();
    if (!frame) return false;
    try {
      frame.contentWindow.postMessage({ type: 'aiteacher-highlight', query }, '*');
    } catch (_) { return false; }
    return true;
  }

  // hint/reveal/step 交给课件的 __aiteacherCmd，由注入的桥接脚本转发并回执。
  // 课件在 manifest 里声明了自己支持哪些指令，服务端随材料数据下发 commands。
  // 字段缺失（列表接口不给派生数据）时照常投递，由课件的 handled 回执兜底。
  function materialSupports(action) {
    const commands = (state.material || {}).commands;
    if (!Array.isArray(commands)) return true;
    return commands.includes(action);
  }

  function sendMaterialCommand(action, value) {
    const frame = activeMaterialFrame();
    if (!frame) return false;
    if (!materialSupports(action)) {
      showToast('这个课件还不能这样操作，老师直接用文字讲给你听');
      return false;
    }
    try {
      frame.contentWindow.postMessage({ type: 'aiteacher-cmd', action, value }, '*');
    } catch (_) { return false; }
    return true;
  }

  // 游标式派发：流式回复每收到一段就全量重解析，只发新增部分，避免重复高亮。
  function dispatchDirectives(parsed, sentHighlights, sentCommands) {
    for (let i = sentHighlights; i < parsed.queries.length; i += 1) {
      highlightInMaterial(parsed.queries[i]);
    }
    for (let i = sentCommands; i < parsed.commands.length; i += 1) {
      sendMaterialCommand(parsed.commands[i].type, parsed.commands[i].value);
    }
  }

  function addMessage(role, content, options = {}) {
    const article = document.createElement('article');
    article.className = `message ${role === 'assistant' ? 'assistant-message' : 'user-message'}`;
    if (options.learningAction) article.classList.add('learning-action');
    const tagHtml = options.learningAction ? '<span class="learning-tag">来自学习区</span>'
      : options.proactive ? '<span class="learning-tag">老师在等你</span>' : '';
    const bubbleHtml = `${tagHtml}<div class="bubble"></div>`;
    if (role === 'assistant') {
      article.innerHTML = `<div class="mini-avatar" aria-hidden="true">A</div><div>${bubbleHtml}</div>`;
    } else {
      article.innerHTML = `<div>${bubbleHtml}</div>`;
    }
    $('.bubble', article).textContent = extractHighlightDirectives(content).text;
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
      // 只上报编号，具体教学须知由服务端从该课的 manifest 读出，前端不传递指令文本。
      course_id: course.id,
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
    const refusal = looksLikeRefusal(text);
    if (refusal) clearExpecting();
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
      let sentHighlights = 0;
      let sentCommands = 0;
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
            // 气泡只渲染剥离指令后的文本；新出现的指令立即转发给课件。
            const parsed = extractHighlightDirectives(reply);
            assistantBubble.textContent = parsed.text;
            dispatchDirectives(parsed, sentHighlights, sentCommands);
            sentHighlights = parsed.queries.length;
            sentCommands = parsed.commands.length;
            $('#messages').scrollTop = $('#messages').scrollHeight;
          } else if (data.type === 'error') {
            throw new Error(data.message || 'AI老师暂时没有连上');
          }
        }
      }
      const parsedFinal = extractHighlightDirectives(reply);
      dispatchDirectives(parsedFinal, sentHighlights, sentCommands);
      const finalText = parsedFinal.text.trim();
      if (!finalText) throw new Error('AI老师暂时没有返回内容');
      if (assistantBubble) assistantBubble.textContent = finalText;
      state.messages.push({ role: 'assistant', content: finalText });
      // 老师这句说完后，若孩子刚才是拒绝/暂停则不再追问，否则重新开始观察等待。
      const armAfterSpeak = () => { if (!refusal) beginExpecting(); };
      if (state.autoSpeakReplies) speak(finalText).then(armAfterSpeak);
      else armAfterSpeak();
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
    observeActivity();
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

  // ============================================================
  // 主动等待观察（看门狗）：客户端只把关时机与安全，模型决定说什么。
  // ============================================================
  const PROACTIVE_BASE_DELAY_MS = 10000; // 首次去看之前的保守安静时间
  const PROACTIVE_MIN_CHECK_MS = 4000;
  const PROACTIVE_MAX_CHECK_MS = 30000;
  const PROACTIVE_MAX_NUDGES = 3;        // 与服务端 cap 一致
  const PROACTIVE_MAX_SILENT_CHECKS = 10; // 防止长时间静默时无限轮询
  const REFUSAL_WORDS = ['不要', '不用', '停', '休息', '不想', '不玩', '累'];

  let expectingResponse = false;
  let proactiveTimer = null;
  let promptAtMs = 0;
  let aiDoneAtMs = 0;
  let lastActivityAt = 0;
  let nudgeCount = 0;
  let silentChecks = 0;
  let respondedThisRound = false;
  let usedMicThisRound = false;
  let typedKeystrokes = 0;
  let lessonAttemptBase = 0;
  let latencySamples = [];
  let baselineLatencyMs = 0;

  function nowMs() { return Date.now(); }

  function scheduleNextCheck(ms) {
    if (proactiveTimer) { window.clearTimeout(proactiveTimer); proactiveTimer = null; }
    if (!expectingResponse) return;
    const delay = Math.min(PROACTIVE_MAX_CHECK_MS, Math.max(PROACTIVE_MIN_CHECK_MS, Number(ms) || PROACTIVE_BASE_DELAY_MS));
    proactiveTimer = window.setTimeout(runProactiveCheck, delay);
  }

  function beginExpecting() {
    // v1 只在“结构化体验课 + 开关已开 + 非自选课件”时启动。
    if (!state.proactiveWait || state.materialMode || !currentLesson()) return;
    const now = nowMs();
    expectingResponse = true;
    promptAtMs = now;
    aiDoneAtMs = now;
    lastActivityAt = now;
    nudgeCount = 0;
    silentChecks = 0;
    respondedThisRound = false;
    usedMicThisRound = false;
    typedKeystrokes = 0;
    lessonAttemptBase = state.attempts;
    scheduleNextCheck(PROACTIVE_BASE_DELAY_MS);
  }

  function clearExpecting() {
    expectingResponse = false;
    if (proactiveTimer) { window.clearTimeout(proactiveTimer); proactiveTimer = null; }
  }

  function recordLatencySample(ms) {
    if (!(ms > 200) || ms > 120000) return;
    latencySamples.push(ms);
    if (latencySamples.length > 8) latencySamples.shift();
    const sorted = latencySamples.slice().sort((a, b) => a - b);
    baselineLatencyMs = sorted[Math.floor(sorted.length / 2)] || 0;
  }

  // 任何来自孩子的活动都刷新“最后一次动作”时间；首次动作时记一次响应延迟。
  function observeActivity() {
    if (!expectingResponse) return;
    lastActivityAt = nowMs();
    if (!respondedThisRound) {
      respondedThisRound = true;
      recordLatencySample(lastActivityAt - promptAtMs);
    }
  }

  function looksLikeRefusal(text) {
    const value = String(text || '');
    return REFUSAL_WORDS.some(word => value.includes(word));
  }

  async function runProactiveCheck() {
    proactiveTimer = null;
    if (!state.proactiveWait || !expectingResponse) return;
    // 不打断自己，也不在孩子正在得到回复时插话：顺延再看。
    if (state.busy || activeSources.length > 0) { scheduleNextCheck(PROACTIVE_MIN_CHECK_MS); return; }
    silentChecks += 1;
    if (silentChecks > PROACTIVE_MAX_SILENT_CHECKS) { clearExpecting(); return; }
    const now = nowMs();
    const secondsSince = ms => Math.max(0, Math.round((now - ms) / 1000));
    const body = {
      page_context: pageContext(),
      silence: {
        since_prompt_s: secondsSince(promptAtMs),
        since_ai_done_s: secondsSince(aiDoneAtMs),
        since_any_action_s: secondsSince(lastActivityAt),
        nudge_count: nudgeCount,
      },
      engagement: {
        last_action: state.lastAction,
        constructed_phrase: state.constructedPhrase.join(''),
        partial_attempt: state.constructedPhrase.length > 0,
        answered_last_turn: respondedThisRound,
        mic_used: usedMicThisRound,
        typed_keystrokes: typedKeystrokes,
        attempts_this_lesson: Math.max(0, state.attempts - lessonAttemptBase),
        baseline_latency_ms: baselineLatencyMs,
      },
      history: state.messages.slice(-6),
    };
    try {
      const response = await fetch('/aiteacher/api/nudge', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const decision = await response.json().catch(() => ({}));
      applyNudgeDecision(decision);
    } catch (_) {
      // 网络/服务异常：安全地“再等等”。
      applyNudgeDecision({ should_speak: false, await_reply: true, next_check_in_ms: PROACTIVE_BASE_DELAY_MS });
    }
  }

  function applyNudgeDecision(decision) {
    if (!expectingResponse) return;
    const d = decision || {};
    if (d.should_speak && d.text) {
      nudgeCount += 1;
      const parsed = extractHighlightDirectives(String(d.text));
      addMessage('assistant', parsed.text, { proactive: true });
      parsed.queries.forEach(query => highlightInMaterial(query));
      parsed.commands.forEach(cmd => sendMaterialCommand(cmd.type, cmd.value));
      if (state.autoVoice) {
        speak(parsed.text, true).then(() => {
          aiDoneAtMs = nowMs();
          afterNudgeSpoken(d);
        });
      } else {
        afterNudgeSpoken(d);
      }
      return;
    }
    if (d.handoff) { handleHandoff(d.handoff); return; }
    if (d.await_reply === false) { clearExpecting(); return; }
    scheduleNextCheck(d.next_check_in_ms || PROACTIVE_BASE_DELAY_MS);
  }

  function afterNudgeSpoken(d) {
    if (!expectingResponse) return;
    if (d.handoff) { handleHandoff(d.handoff); return; }
    if (nudgeCount >= PROACTIVE_MAX_NUDGES) { handleHandoff('caregiver'); return; }
    if (d.await_reply === false) { clearExpecting(); return; }
    scheduleNextCheck(d.next_check_in_ms || PROACTIVE_BASE_DELAY_MS);
  }

  function handleHandoff(kind) {
    if (kind === 'break') {
      const msg = '有点累了吗？我们先停一下，准备好了再回来。';
      addMessage('assistant', msg, { proactive: true });
      if (state.autoVoice) speak(msg, true);
    } else {
      // 交还给照护者：不在孩子面前反复说，只给大人一个轻提示。
      showToast('孩子可能在想，先把安静留给 TA');
    }
    clearExpecting();
  }

  async function startRecording() {
    // 孩子准备说话了：立刻停止老师当前的语音。
    stopSpeaking();
    observeActivity();
    usedMicThisRound = true;
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
    clearExpecting();
    $('#learnerName').value = state.preferences.name || '';
    $('#learnerInterests').value = state.preferences.interests || '';
    $('#speechRate').value = String(state.preferences.speechRate || 0.86);
    $('#autoSpeakReplies').checked = state.autoSpeakReplies;
    $('#proactiveWait').checked = state.proactiveWait;
    $$('input[name="mode"]').forEach(box => { box.checked = state.preferences.modes.includes(box.value); });
    $('#profileDialog').showModal();
    loadMemoryPanel();
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
    state.autoSpeakReplies = $('#autoSpeakReplies').checked;
    state.proactiveWait = $('#proactiveWait').checked;
    // 根据开关及时调整看门狗：关闭就停，打开就为当前环节重新开始观察。
    if (state.proactiveWait && !state.materialMode) beginExpecting(); else clearExpecting();
    persistState();
    $('#profileDialog').close();
    showToast('学习偏好已保存');
  }

  function renderMemory(profile) {
    const panel = $('#memoryPanel');
    const list = $('#memoryList');
    const entries = [];
    Object.keys(profile || {}).forEach(category => {
      (profile[category] || []).forEach(entry => {
        if (entry && entry.item) entries.push(entry);
      });
    });
    if (!entries.length) {
      panel.hidden = true;
      list.innerHTML = '';
      return;
    }
    panel.hidden = false;
    list.innerHTML = entries.map(entry =>
      '<div class="memory-item"><span class="memory-tag">%s</span>%s</div>'
    ).join('');
    // 用 textContent 写内容，避免把记忆文本当作 HTML 解析。
    $$('.memory-item', list).forEach((node, index) => {
      node.querySelector('.memory-tag').textContent = entries[index].label || '';
      node.appendChild(document.createTextNode(entries[index].item));
    });
  }

  async function loadMemoryPanel() {
    try {
      const response = await fetch('/aiteacher/api/memory');
      const data = await response.json();
      if (data && data.success) renderMemory(data.profile);
      else $('#memoryPanel').hidden = true;
    } catch (_) {
      $('#memoryPanel').hidden = true;
    }
  }

  async function clearMyMemory() {
    if (!window.confirm('确定清除 AI 老师对你的全部记忆吗？此操作不可撤销。')) return;
    try {
      const response = await fetch('/aiteacher/api/memory', { method: 'DELETE' });
      const data = await response.json();
      if (data && data.success) {
        renderMemory({});
        showToast('已清除我的记忆');
      } else {
        showToast('清除失败，请稍后再试');
      }
    } catch (_) {
      showToast('清除失败，请稍后再试');
    }
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

  function clearConversation() {
    const box = $('#messages');
    if (box) box.innerHTML = '';
    state.messages = [];
  }

  // 拉取并渲染某教程的历史聊天；有历史则恢复，无历史返回 false 交给调用方处理。
  async function restoreChatHistory(materialId) {
    clearConversation();
    let msgs = [];
    try {
      const response = await fetch('/aiteacher/api/chat/history?doc_id=' + encodeURIComponent(materialId));
      const data = await response.json();
      if (data && data.success) msgs = data.messages || [];
    } catch (_) { /* 没有历史时保持空白 */ }
    if (!msgs.length) return false;
    msgs.forEach(item => addMessage(item.role, item.content));
    $('#messages').scrollTop = $('#messages').scrollHeight;
    return true;
  }

  async function showMaterial(material, options = {}) {
    clearExpecting();
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
    $('#materialFrameLoading').hidden = false;
    $('#materialFrame').src = `${material.viewer_url}?v=${Date.now()}`;
    state.lastAction = `打开了学习材料“${material.title}”`;
    pulseContext();
    // 先尝试恢复这个教程上次的聊天历史；没有历史才给开场引导。
    const restored = await restoreChatHistory(material.id);
    if (!restored && !options.silent) {
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
    // 首次用户手势时解锁 Web Audio，保证后续流式回复的语音能自动播放。
    ['pointerdown', 'keydown', 'touchstart'].forEach(type => {
      document.addEventListener(type, unlockAudio, { once: true, passive: true });
    });
    $('#sendButton').addEventListener('click', sendComposerMessage);
    $('#messageInput').addEventListener('keydown', event => {
      if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); sendComposerMessage(); }
    });
    $('#messageInput').addEventListener('input', event => {
      observeActivity();
      typedKeystrokes += 1;
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
      updateVoiceToggle();
      if (!state.autoVoice) { stopSpeaking(); clearExpecting(); }
      persistState();
      showToast(state.autoVoice ? '老师语音已开启' : '老师语音已关闭');
    });
    $('#voiceTimbreToggle').addEventListener('click', event => {
      event.stopPropagation();
      unlockAudio();
      toggleTimbreMenu();
    });
    document.addEventListener('click', event => {
      const wrap = $('.voice-timbre-wrap');
      if (wrap && !wrap.contains(event.target)) closeTimbreMenu();
    });
    document.addEventListener('keydown', event => { if (event.key === 'Escape') closeTimbreMenu(); });
    $('#voiceBanner').addEventListener('click', async () => {
      unlockAudio();
      if (await audioReady()) {
        const retry = pendingSpeech;
        hideVoiceBanner();
        if (retry) speak(retry, true);
      } else {
        showToast('还是播不出声音，请旁边的大人帮忙检查设备音量');
      }
    });
    $('#micButton').addEventListener('click', startRecording);
    $('#stopRecording').addEventListener('click', stopRecording);
    $('#profileForm').addEventListener('submit', saveProfile);
    $('#clearMemoryBtn').addEventListener('click', clearMyMemory);
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
      if (payload.type === 'aiteacher-highlight-result') {
        // 课件里没找到：提醒换个说法，老师下次会重试。
        if (!payload.count && payload.query) {
          showToast(`课件里没找到“${payload.query}”，让老师换个说法试试`);
        }
        return;
      }
      if (payload.type === 'aiteacher-cmd-result') {
        // 课件没实现这个操作：明说一声，别让指令静悄悄失败。
        if (!payload.handled && payload.action) {
          showToast('这个课件还不能这样操作，老师直接用文字讲给你听');
        }
        return;
      }
      if (payload.type !== 'aiteacher-learning-action') return;
      // 孩子在课件里操作就是“有反应”，否则沉默观察会误判成走神、突然插话。
      observeActivity();
      const action = String(payload.action || '').slice(0, 300);
      const spoken = String(payload.spoken || '').slice(0, 300);
      if (action) {
        state.lastAction = action;
        pulseContext();
      }
      // spoken 只负责“把这句话读出来”；respond 得独立生效——课件里“连错两次”“要提示”
      // 这类事件并没有要朗读的话，但仍要把老师叫过来，不能被 spoken 非空卡住。
      if (spoken) speak(spoken, true);
      if (payload.respond) {
        const prompt = spoken || action;
        if (prompt) {
          state.attempts += 1;
          addMessage('user', prompt, { learningAction: true });
          requestTeacherResponse(prompt, { alreadyRendered: true });
        }
      }
    });
  }

  function setupPanels() {
    const classroom = $('#classroom');
    const divider = $('#panelDivider');
    const toggle = $('#dividerToggle');
    if (!classroom || !divider || !toggle) return;
    const widthKey = 'aiteacher-chat-w';
    const collapsedKey = 'aiteacher-chat-collapsed';

    const readStoredWidth = () => {
      const saved = parseInt(localStorage.getItem(widthKey), 10);
      return Number.isFinite(saved) && saved > 0 ? saved : 0;
    };
    const clamp = w => {
      const min = 300;
      const max = Math.max(min + 40, classroom.clientWidth - 440);
      return Math.min(Math.max(min, w), max);
    };
    const resolveWidth = () => readStoredWidth() || clamp(Math.round(classroom.clientWidth * 0.39));

    let collapsed = localStorage.getItem(collapsedKey) === '1';

    const paintToggle = () => {
      const label = collapsed ? '展开聊天区' : '收缩聊天区';
      toggle.title = label;
      toggle.setAttribute('aria-label', label);
      toggle.setAttribute('aria-expanded', String(!collapsed));
    };

    const apply = () => {
      classroom.classList.toggle('chat-collapsed', collapsed);
      if (!collapsed) classroom.style.setProperty('--chat-w', `${clamp(resolveWidth())}px`);
      paintToggle();
    };

    apply();

    let dragging = false;
    divider.addEventListener('pointerdown', event => {
      if (event.target.closest('.divider-toggle')) return;
      dragging = true;
      try { divider.setPointerCapture(event.pointerId); } catch (_) { /* ignore */ }
      if (collapsed) { collapsed = false; localStorage.setItem(collapsedKey, '0'); }
      classroom.classList.remove('chat-collapsed');
      document.body.classList.add('is-resizing');
    });
    divider.addEventListener('pointermove', event => {
      if (!dragging) return;
      const rect = classroom.getBoundingClientRect();
      const w = clamp(event.clientX - rect.left);
      classroom.style.setProperty('--chat-w', `${w}px`);
      localStorage.setItem(widthKey, String(w));
    });
    const endDrag = event => {
      if (!dragging) return;
      dragging = false;
      try { divider.releasePointerCapture(event.pointerId); } catch (_) { /* ignore */ }
      document.body.classList.remove('is-resizing');
    };
    divider.addEventListener('pointerup', endDrag);
    divider.addEventListener('pointercancel', endDrag);

    const toggleCollapse = () => {
      if (!collapsed) localStorage.setItem(widthKey, String(clamp(resolveWidth())));
      collapsed = !collapsed;
      localStorage.setItem(collapsedKey, collapsed ? '1' : '0');
      apply();
    };
    toggle.addEventListener('click', event => { event.stopPropagation(); toggleCollapse(); });

    divider.addEventListener('keydown', event => {
      if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
        const base = collapsed ? 300 : (parseInt(classroom.style.getPropertyValue('--chat-w'), 10) || resolveWidth());
        const w = clamp(base + (event.key === 'ArrowLeft' ? -32 : 32));
        if (collapsed) { collapsed = false; localStorage.setItem(collapsedKey, '0'); }
        localStorage.setItem(widthKey, String(w));
        apply();
        event.preventDefault();
      } else if (event.key === 'Enter' || event.key === ' ') {
        toggleCollapse();
        event.preventDefault();
      }
    });

    window.addEventListener('resize', () => { if (!collapsed) apply(); });
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
  updateVoiceToggle();
  updateTimbreButton();
  loadVoiceOptions();
  bindEvents();
  setupPanels();
  renderLesson();
  refreshAccount();
  openDefaultBuiltin();
})();
