(() => {
  const WS_URL = `ws://${location.host}/ws`;
  const RECONNECT_DELAY_MS = 3000;

  const term = new Terminal({
    theme: {
      background: "#0d0d0d",
      foreground: "#d4c9a8",
      cursor: "#c8a96e",
      cursorAccent: "#0d0d0d",
      black: "#1a1a1a",
      red: "#c0392b",
      green: "#4a8c5c",
      yellow: "#c8a96e",
      blue: "#4a6fa5",
      magenta: "#8b5e83",
      cyan: "#4a8c8c",
      white: "#d4c9a8",
      brightBlack: "#555555",
      brightRed: "#e74c3c",
      brightGreen: "#5dade2",
      brightYellow: "#f0c040",
      brightBlue: "#5b8dd9",
      brightMagenta: "#b07cc6",
      brightCyan: "#5dade2",
      brightWhite: "#f5f0e8",
    },
    fontFamily: '"Cascadia Code", "Fira Code", "Consolas", monospace',
    fontSize: 14,
    lineHeight: 1.25,
    cursorBlink: true,
    cursorStyle: "block",
    scrollback: 2000,
    convertEol: true,
  });

  const fitAddon = new FitAddon.FitAddon();
  term.loadAddon(fitAddon);
  term.open(document.getElementById("terminal"));
  fitAddon.fit();

  window.addEventListener("resize", () => fitAddon.fit());

  const statusBar = document.getElementById("status-bar");
  const connLabel = document.getElementById("conn-label");

  let ws = null;
  let inputBuffer = "";
  let reconnectTimer = null;

  function setStatus(connected) {
    if (connected) {
      statusBar.textContent = "Connected to server";
      statusBar.className = "connected";
      connLabel.textContent = "● Connected";
    } else {
      statusBar.textContent = `Disconnected — reconnecting in ${RECONNECT_DELAY_MS / 1000}s...`;
      statusBar.className = "disconnected";
      connLabel.textContent = "○ Disconnected";
    }
  }

  function connect() {
    if (ws) {
      try { ws.close(); } catch (_) {}
    }
    ws = new WebSocket(WS_URL);

    ws.onopen = () => {
      setStatus(true);
      term.focus();
    };

    ws.onmessage = (evt) => {
      if (typeof evt.data === "string") {
        // Server sends plain text with \n — write directly; xterm handles convertEol
        term.write(evt.data);
      }
    };

    ws.onerror = () => {
      // onclose fires after onerror, handled there
    };

    ws.onclose = () => {
      setStatus(false);
      scheduleReconnect();
    };
  }

  function scheduleReconnect() {
    if (reconnectTimer) return;
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      connect();
    }, RECONNECT_DELAY_MS);
  }

  function sendLine(line) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(line);
    }
  }

  // Handle keyboard input
  term.onKey(({ key, domEvent }) => {
    const code = domEvent.keyCode;

    if (code === 13) {
      // Enter — send buffered line, echo newline
      term.write("\r\n");
      sendLine(inputBuffer);
      inputBuffer = "";
    } else if (code === 8) {
      // Backspace
      if (inputBuffer.length > 0) {
        inputBuffer = inputBuffer.slice(0, -1);
        term.write("\b \b"); // erase last char on screen
      }
    } else if (code === 38 || code === 40) {
      // Up/Down arrows — ignore (no history for now)
    } else if (domEvent.ctrlKey && code === 67) {
      // Ctrl+C — clear buffer and send empty line
      inputBuffer = "";
      term.write("^C\r\n");
    } else if (key && key.length === 1) {
      // Printable character — echo locally and buffer
      inputBuffer += key;
      term.write(key);
    }
  });

  // Paste support
  term.onData((data) => {
    // onKey handles single chars; onData catches paste events
    // Filter out chars already handled by onKey (single char, Enter, Backspace)
    if (data.length <= 1) return; // handled by onKey
    // Multi-char paste
    for (const ch of data) {
      if (ch === "\r" || ch === "\n") {
        term.write("\r\n");
        sendLine(inputBuffer);
        inputBuffer = "";
      } else if (ch === "\b" || ch.charCodeAt(0) === 127) {
        if (inputBuffer.length > 0) {
          inputBuffer = inputBuffer.slice(0, -1);
          term.write("\b \b");
        }
      } else {
        inputBuffer += ch;
        term.write(ch);
      }
    }
  });

  connect();
})();
