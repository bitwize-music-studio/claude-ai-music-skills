// ==UserScript==
// @name         Suno Auto-Fill (bitwize-music)
// @namespace    https://github.com/bitwize-music-studio
// @version      1.0.0
// @description  Auto-fill Suno's create page with title, style, and lyrics from clipboard JSON
// @author       bitwize
// @match        https://suno.com/create*
// @grant        none
// ==/UserScript==

(function () {
  'use strict';

  // =========================================================================
  // Configuration — update selectors here if Suno's DOM changes
  // =========================================================================
  const CONFIG = {
    // Each field tries strategies in order until one matches.
    // Strategy: { method, value } where method is a querySelector approach.
    fields: {
      title: [
        { method: 'aria-label', value: 'Title' },
        { method: 'placeholder', value: 'Title' },
        { method: 'data-testid', value: 'song-title' },
        { method: 'class-contains', value: 'title' },
        { method: 'dom-position', value: 'first-input' },
      ],
      style: [
        { method: 'aria-label', value: 'Style of Music' },
        { method: 'placeholder', value: 'Style of Music' },
        { method: 'data-testid', value: 'style-prompt' },
        { method: 'class-contains', value: 'style' },
        { method: 'dom-position', value: 'first-textarea' },
      ],
      lyrics: [
        { method: 'aria-label', value: 'Lyrics' },
        { method: 'placeholder', value: 'Lyrics' },
        { method: 'data-testid', value: 'lyrics' },
        { method: 'class-contains', value: 'lyrics' },
        { method: 'dom-position', value: 'second-textarea' },
      ],
    },
    buttonPosition: { bottom: '20px', right: '20px' },
  };

  // =========================================================================
  // Selector resolution — tries each strategy until a match is found
  // =========================================================================
  function findField(strategies) {
    for (const strategy of strategies) {
      let el = null;
      switch (strategy.method) {
        case 'aria-label':
          el = document.querySelector(
            `input[aria-label*="${strategy.value}" i], textarea[aria-label*="${strategy.value}" i]`
          );
          break;
        case 'placeholder':
          el = document.querySelector(
            `input[placeholder*="${strategy.value}" i], textarea[placeholder*="${strategy.value}" i]`
          );
          break;
        case 'data-testid':
          el = document.querySelector(`[data-testid*="${strategy.value}"]`);
          if (el && el.tagName !== 'INPUT' && el.tagName !== 'TEXTAREA') {
            el = el.querySelector('input, textarea') || el;
          }
          break;
        case 'class-contains': {
          const all = document.querySelectorAll('input, textarea');
          el = Array.from(all).find(
            (e) =>
              e.className
                .toLowerCase()
                .includes(strategy.value.toLowerCase()) ||
              (e.parentElement &&
                e.parentElement.className
                  .toLowerCase()
                  .includes(strategy.value.toLowerCase()))
          );
          break;
        }
        case 'dom-position':
          if (strategy.value === 'first-input') {
            el = document.querySelector('input[type="text"], input:not([type])');
          } else if (strategy.value === 'first-textarea') {
            el = document.querySelector('textarea');
          } else if (strategy.value === 'second-textarea') {
            const textareas = document.querySelectorAll('textarea');
            el = textareas.length >= 2 ? textareas[1] : null;
          }
          break;
      }
      if (el) {
        console.log(
          `[suno-autofill] Found field via ${strategy.method}="${strategy.value}"`,
          el
        );
        return el;
      }
    }
    return null;
  }

  // =========================================================================
  // React-compatible value setter
  // Suno is a React/Next.js app — direct .value assignment is ignored.
  // We use the native input value setter and dispatch synthetic events.
  // =========================================================================
  function setFieldValue(el, value) {
    const nativeSetter =
      Object.getOwnPropertyDescriptor(
        el.tagName === 'TEXTAREA'
          ? HTMLTextAreaElement.prototype
          : HTMLInputElement.prototype,
        'value'
      )?.set;

    if (nativeSetter) {
      nativeSetter.call(el, value);
    } else {
      el.value = value;
    }

    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  }

  // =========================================================================
  // Toast notification
  // =========================================================================
  function showToast(message, isError = false) {
    const toast = document.createElement('div');
    toast.textContent = message;
    Object.assign(toast.style, {
      position: 'fixed',
      bottom: '70px',
      right: '20px',
      padding: '12px 20px',
      borderRadius: '8px',
      color: '#fff',
      backgroundColor: isError ? '#e53e3e' : '#38a169',
      fontSize: '14px',
      fontWeight: '500',
      zIndex: '100000',
      boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
      transition: 'opacity 0.3s ease',
    });
    document.body.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }

  // =========================================================================
  // Main auto-fill logic
  // =========================================================================
  async function autoFill() {
    let clipText;
    try {
      clipText = await navigator.clipboard.readText();
    } catch (err) {
      showToast('Clipboard access denied. Check browser permissions.', true);
      console.error('[suno-autofill] Clipboard read failed:', err);
      return;
    }

    let data;
    try {
      data = JSON.parse(clipText);
    } catch {
      showToast('Clipboard does not contain valid JSON. Use /clipboard suno first.', true);
      return;
    }

    if (!data.title && !data.style && !data.lyrics) {
      showToast('JSON missing title/style/lyrics fields.', true);
      return;
    }

    let filled = 0;
    const missing = [];

    for (const [fieldName, value] of Object.entries(data)) {
      if (!value || !CONFIG.fields[fieldName]) continue;
      const el = findField(CONFIG.fields[fieldName]);
      if (el) {
        setFieldValue(el, value);
        filled++;
      } else {
        missing.push(fieldName);
      }
    }

    if (filled > 0 && missing.length === 0) {
      showToast(`Filled ${filled} field(s) successfully.`);
    } else if (filled > 0) {
      showToast(
        `Filled ${filled} field(s). Could not find: ${missing.join(', ')}. Run debugFields() in console.`,
        true
      );
    } else {
      showToast(
        'No fields found on page. Run debugFields() in console for help.',
        true
      );
    }
  }

  // =========================================================================
  // Debug helper — logs all inputs/textareas for selector discovery
  // =========================================================================
  window.debugFields = function () {
    console.group('[suno-autofill] Field Debug Report');
    const inputs = document.querySelectorAll('input, textarea');
    inputs.forEach((el, i) => {
      console.log(`#${i}`, {
        tag: el.tagName,
        type: el.type,
        placeholder: el.placeholder,
        ariaLabel: el.getAttribute('aria-label'),
        testId: el.getAttribute('data-testid'),
        className: el.className,
        name: el.name,
        id: el.id,
        parentClass: el.parentElement?.className,
      });
    });
    console.groupEnd();
    console.log(
      '[suno-autofill] Update CONFIG.fields in the script with matching selectors.'
    );
  };

  // =========================================================================
  // Floating "Paste Track" button
  // =========================================================================
  function createButton() {
    const btn = document.createElement('button');
    btn.textContent = 'Paste Track';
    Object.assign(btn.style, {
      position: 'fixed',
      bottom: CONFIG.buttonPosition.bottom,
      right: CONFIG.buttonPosition.right,
      padding: '10px 18px',
      borderRadius: '8px',
      border: 'none',
      backgroundColor: '#5a67d8',
      color: '#fff',
      fontSize: '14px',
      fontWeight: '600',
      cursor: 'pointer',
      zIndex: '99999',
      boxShadow: '0 2px 8px rgba(0,0,0,0.3)',
      transition: 'background-color 0.2s ease',
    });
    btn.addEventListener('mouseenter', () => {
      btn.style.backgroundColor = '#4c51bf';
    });
    btn.addEventListener('mouseleave', () => {
      btn.style.backgroundColor = '#5a67d8';
    });
    btn.addEventListener('click', autoFill);
    btn.title = 'Paste track data from clipboard (Ctrl+Shift+V)';
    document.body.appendChild(btn);
  }

  // =========================================================================
  // Keyboard shortcut: Ctrl+Shift+V
  // =========================================================================
  document.addEventListener('keydown', (e) => {
    if (e.ctrlKey && e.shiftKey && e.key === 'V') {
      e.preventDefault();
      autoFill();
    }
  });

  // =========================================================================
  // Initialize when page is ready
  // =========================================================================
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', createButton);
  } else {
    createButton();
  }
})();
