/**
 * 可拖分栏 + 对话区自动滚底（滚动容器 = st.container 的 BorderWrapper）
 */
(() => {
  const doc = window.parent.document;
  const root = doc.documentElement;
  const KEY = "ct-sidebar-w";
  const DEFAULT_W = 280;
  const MIN_W = 200;
  const MAX_RATIO = 0.55;
  const SCROLL_ATTR = "data-ct-chat-scroll";

  function loadWidth() {
    const saved = parseInt(localStorage.getItem(KEY) || "", 10);
    if (!Number.isNaN(saved) && saved >= MIN_W) {
      root.style.setProperty("--ct-sidebar-w", `${saved}px`);
    }
  }

  function findMainSplitRow() {
    const blocks = doc.querySelectorAll(
      "section.main .block-container div[data-testid='stHorizontalBlock']"
    );
    for (const block of blocks) {
      const cols = block.querySelectorAll(":scope > div[data-testid='column']");
      if (cols.length !== 2) continue;
      if (cols[0].querySelector("[data-testid='stTabs']")) return block;
    }
    return null;
  }

  function getChatColumn(block) {
    if (!block) return null;
    const cols = block.querySelectorAll(":scope > div[data-testid='column']");
    return cols.length >= 2 ? cols[cols.length - 1] : null;
  }

  /** 右侧 st.container(height=…) 的真实滚动节点 */
  function findChatScrollEl() {
    const col = getChatColumn(findMainSplitRow());
    if (!col) return null;
    const wrapper = col.querySelector('[data-testid="stVerticalBlockBorderWrapper"]');
    if (wrapper) return wrapper;
    return col;
  }

  function clampWidth(block, w) {
    const maxW = Math.floor(block.getBoundingClientRect().width * MAX_RATIO);
    return Math.min(maxW, Math.max(MIN_W, w));
  }

  function setWidth(block, w) {
    const clamped = clampWidth(block, w);
    root.style.setProperty("--ct-sidebar-w", `${clamped}px`);
    localStorage.setItem(KEY, String(clamped));
    return clamped;
  }

  function isNearBottom(el, threshold = 160) {
    return el.scrollHeight - el.scrollTop - el.clientHeight < threshold;
  }

  function scrollChatToBottom(force = false) {
    const el = findChatScrollEl();
    if (!el) return;
    if (force || isNearBottom(el)) {
      el.scrollTop = el.scrollHeight;
    }
  }

  function initLayoutRow() {
    const block = findMainSplitRow();
    if (block) block.classList.add("ct-split-row", "ct-layout-row");
  }

  function initChatAutoScroll() {
    const el = findChatScrollEl();
    if (!el) return;

    el.classList.add("ct-chat-scroll-root");

    if (el.getAttribute(SCROLL_ATTR) === "1") {
      requestAnimationFrame(() => scrollChatToBottom(false));
      return;
    }
    el.setAttribute(SCROLL_ATTR, "1");

    requestAnimationFrame(() => scrollChatToBottom(true));

    let t = null;
    new MutationObserver(() => {
      clearTimeout(t);
      t = setTimeout(() => scrollChatToBottom(false), 80);
    }).observe(el, { childList: true, subtree: true, characterData: true });
  }

  function initSplitter() {
    if (window.innerWidth <= 900) return;
    const block = findMainSplitRow();
    if (!block) return;

    const cols = block.querySelectorAll(":scope > div[data-testid='column']");
    if (cols.length < 2) return;

    let handle = block.querySelector(":scope > div.ct-splitter");
    if (!handle) {
      handle = doc.createElement("div");
      handle.className = "ct-splitter";
      handle.title = "拖动调整左右栏宽度";
      cols[0].insertAdjacentElement("afterend", handle);
    }

    if (handle.dataset.bound === "1") return;
    handle.dataset.bound = "1";

    let dragging = false;
    handle.addEventListener("mousedown", (e) => {
      dragging = true;
      handle.classList.add("ct-dragging");
      doc.body.style.cursor = "col-resize";
      e.preventDefault();
    });
    doc.addEventListener("mousemove", (e) => {
      if (!dragging) return;
      setWidth(block, e.clientX - block.getBoundingClientRect().left);
    });
    doc.addEventListener("mouseup", () => {
      if (!dragging) return;
      dragging = false;
      handle.classList.remove("ct-dragging");
      doc.body.style.cursor = "";
    });
    handle.addEventListener("dblclick", () => setWidth(block, DEFAULT_W));
  }

  function initAll() {
    initLayoutRow();
    initSplitter();
    initChatAutoScroll();
  }

  loadWidth();
  let timer = null;
  const schedule = () => {
    clearTimeout(timer);
    timer = setTimeout(initAll, 80);
  };
  schedule();

  const main = doc.querySelector("section.main");
  if (main) {
    new MutationObserver(schedule).observe(main, { childList: true, subtree: true });
  }
  window.addEventListener("resize", schedule);
})();
