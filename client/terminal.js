(() => {
  const WS_URL = `ws://${location.host}/ws`;
  const RECONNECT_DELAY_MS = 3000;

  // Output terminal (for server messages)
  const outputTerm = new Terminal({
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
    cursorBlink: false,
    cursorStyle: "block",
    scrollback: 5000,
    convertEol: true,
    disableStdin: true,  // Read-only output terminal
  });

  // Input terminal (for user typing)
  const inputTerm = new Terminal({
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
    scrollback: 100,
    convertEol: true,
    rows: 1,  // Start with 1 row, will expand
  });

  const outputFitAddon = new FitAddon.FitAddon();
  const inputFitAddon = new FitAddon.FitAddon();
  
  outputTerm.loadAddon(outputFitAddon);
  inputTerm.loadAddon(inputFitAddon);
  
  outputTerm.open(document.getElementById("terminal-output"));
  inputTerm.open(document.getElementById("terminal-input"));
  
  outputFitAddon.fit();
  inputFitAddon.fit();

  window.addEventListener("resize", () => {
    outputFitAddon.fit();
    inputFitAddon.fit();
  });

  const statusBar = document.getElementById("status-bar");
  const connLabel = document.getElementById("conn-label");

  let ws = null;
  let inputBuffer = "";
  let reconnectTimer = null;

  // Command history tracking
  let commandHistory = [];        // Array of sent commands
  let historyIndex = -1;           // Current position (-1 = not navigating)
  const MAX_HISTORY = 50;          // Maximum commands to remember

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
      inputTerm.focus();
      // Initialize context panel
      if (window.ContextPanel) {
        window.ContextPanel.init();
      }
    };

    ws.onmessage = (evt) => {
      if (typeof evt.data === "string") {
        const data = evt.data.trim();
        
        // Check if it's a JSON message (starts with {)
        if (data.startsWith('{')) {
          try {
            const msg = JSON.parse(data);
            if (msg.type === 'context' && window.ContextPanel) {
              window.ContextPanel.update(msg.data);
              return;  // Don't print JSON to terminal
            }
          } catch (e) {
            // Not valid JSON, treat as text
          }
        }
        
        // Regular text message - write to output terminal
        outputTerm.write(evt.data);
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

  // Handle keyboard input on input terminal only
  inputTerm.onKey(({ key, domEvent }) => {
    const code = domEvent.keyCode;

    if (code === 13) {
      // Enter — send buffered line, clear input terminal
      inputTerm.write("\r\n");
      
      // Save to history if input is not empty
      const trimmedInput = inputBuffer.trim();
      if (trimmedInput) {
        // Only add if different from most recent command (prevents duplicates)
        if (commandHistory.length === 0 || commandHistory[commandHistory.length - 1] !== trimmedInput) {
          commandHistory.push(trimmedInput);
          // Remove oldest if exceeding max
          if (commandHistory.length > MAX_HISTORY) {
            commandHistory.shift();
          }
        }
        historyIndex = -1;  // Reset navigation position
      }
      
      sendLine(inputBuffer);
      inputBuffer = "";
      // Clear input terminal and reset to 1 row
      inputTerm.clear();
      inputTerm.resize(inputTerm.cols, 1);
    } else if (code === 8) {
      // Backspace
      if (inputBuffer.length > 0) {
        inputBuffer = inputBuffer.slice(0, -1);
        inputTerm.write("\b \b");
      }
    } else if (code === 38) {
      // Up arrow — navigate to previous command
      if (historyIndex < commandHistory.length - 1) {
        historyIndex++;
        inputBuffer = commandHistory[commandHistory.length - 1 - historyIndex];
        // Clear and rewrite input terminal
        inputTerm.clear();
        inputTerm.write(inputBuffer);
        // Adjust rows if needed
        const lines = Math.ceil(inputBuffer.length / inputTerm.cols);
        if (lines > inputTerm.rows && inputTerm.rows < 5) {
          inputTerm.resize(inputTerm.cols, Math.min(lines, 5));
        } else if (lines < inputTerm.rows && inputTerm.rows > 1) {
          inputTerm.resize(inputTerm.cols, Math.max(lines, 1));
        }
      }
    } else if (code === 40) {
      // Down arrow — navigate forward in history
      if (historyIndex > 0) {
        historyIndex--;
        inputBuffer = commandHistory[commandHistory.length - 1 - historyIndex];
        // Clear and rewrite input terminal
        inputTerm.clear();
        inputTerm.write(inputBuffer);
        // Adjust rows if needed
        const lines = Math.ceil(inputBuffer.length / inputTerm.cols);
        if (lines > inputTerm.rows && inputTerm.rows < 5) {
          inputTerm.resize(inputTerm.cols, Math.min(lines, 5));
        } else if (lines < inputTerm.rows && inputTerm.rows > 1) {
          inputTerm.resize(inputTerm.cols, Math.max(lines, 1));
        }
      } else if (historyIndex === 0) {
        // At end of history, clear input
        historyIndex = -1;
        inputBuffer = "";
        inputTerm.clear();
        inputTerm.resize(inputTerm.cols, 1);
      }
    } else if (domEvent.ctrlKey && code === 67) {
      // Ctrl+C — clear buffer and send empty line
      inputBuffer = "";
      inputTerm.write("^C\r\n");
      inputTerm.clear();
      inputTerm.resize(inputTerm.cols, 1);
    } else if (key && key.length === 1) {
      // Printable character — echo locally and buffer
      inputBuffer += key;
      inputTerm.write(key);
      
      // Auto-expand terminal if text wraps (max 5 rows)
      const lines = Math.ceil(inputBuffer.length / inputTerm.cols);
      if (lines > inputTerm.rows && inputTerm.rows < 5) {
        inputTerm.resize(inputTerm.cols, lines);
      }
    }
  });

  // Paste support
  inputTerm.onData((data) => {
    // onKey handles single chars; onData catches paste events
    if (data.length <= 1) return; // handled by onKey
    // Multi-char paste
    for (const ch of data) {
      if (ch === "\r" || ch === "\n") {
        inputTerm.write("\r\n");
        
        // Save to history if input is not empty (same as regular Enter)
        const trimmedInput = inputBuffer.trim();
        if (trimmedInput) {
          // Only add if different from most recent command
          if (commandHistory.length === 0 || commandHistory[commandHistory.length - 1] !== trimmedInput) {
            commandHistory.push(trimmedInput);
            if (commandHistory.length > MAX_HISTORY) {
              commandHistory.shift();
            }
          }
          historyIndex = -1;
        }
        
        sendLine(inputBuffer);
        inputBuffer = "";
        inputTerm.clear();
        inputTerm.resize(inputTerm.cols, 1);
      } else if (ch === "\b" || ch.charCodeAt(0) === 127) {
        if (inputBuffer.length > 0) {
          inputBuffer = inputBuffer.slice(0, -1);
          inputTerm.write("\b \b");
        }
      } else {
        inputBuffer += ch;
        inputTerm.write(ch);
      }
    }
    
    // Check if need to expand after paste (max 5 rows)
    const lines = Math.ceil(inputBuffer.length / inputTerm.cols);
    if (lines > inputTerm.rows && inputTerm.rows < 5) {
      inputTerm.resize(inputTerm.cols, lines);
    }
  });

  // Focus input terminal on click anywhere in terminal area
  document.getElementById("terminal-area").addEventListener("click", () => {
    inputTerm.focus();
  });

  connect();
})();
