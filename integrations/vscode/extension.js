const vscode = require("vscode");
const cp = require("child_process");

let rightPanel;

function workspaceCwd() {
  const folders = vscode.workspace.workspaceFolders;
  return folders && folders.length ? folders[0].uri.fsPath : process.cwd();
}

function config() {
  const cfg = vscode.workspace.getConfiguration("helix");
  return {
    executable: cfg.get("executable") || "helix",
    provider: cfg.get("provider") || "",
    model: cfg.get("model") || ""
  };
}

function runHelix(args, options = {}) {
  return new Promise((resolve, reject) => {
    const cfg = config();
    const finalArgs = [...args];
    const nested = finalArgs[0] === "code";
    const acceptsModelFlags = ["ask", "agent", "code", "subagents"].includes(finalArgs[0]);
    if (cfg.provider && acceptsModelFlags) {
      const insertAt = nested ? 2 : 1;
      finalArgs.splice(insertAt, 0, "--provider", cfg.provider);
    }
    if (cfg.model && acceptsModelFlags) {
      const insertAt = nested ? 2 : 1;
      finalArgs.splice(insertAt, 0, "--model", cfg.model);
    }
    const child = cp.spawn(cfg.executable, finalArgs, {
      cwd: workspaceCwd(),
      shell: process.platform === "win32",
      env: process.env
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", chunk => {
      stdout += chunk.toString();
      if (options.onData) {
        options.onData(chunk.toString());
      }
    });
    child.stderr.on("data", chunk => {
      stderr += chunk.toString();
    });
    child.on("error", reject);
    child.on("close", code => {
      if (code === 0) {
        resolve(stdout.trim());
      } else {
        reject(new Error((stderr || stdout || `Helix exited with ${code}`).trim()));
      }
    });
  });
}

function outputChannel() {
  return vscode.window.createOutputChannel("Helix Agent");
}

function nonce() {
  const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  let value = "";
  for (let i = 0; i < 32; i += 1) {
    value += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return value;
}

class HelixActionItem extends vscode.TreeItem {
  constructor(label, command, icon) {
    super(label, vscode.TreeItemCollapsibleState.None);
    this.command = command;
    this.iconPath = new vscode.ThemeIcon(icon);
  }
}

class HelixPanelProvider {
  constructor() {
    this._onDidChangeTreeData = new vscode.EventEmitter();
    this.onDidChangeTreeData = this._onDidChangeTreeData.event;
  }

  refresh() {
    this._onDidChangeTreeData.fire();
  }

  getTreeItem(element) {
    return element;
  }

  getChildren() {
    return [
      new HelixActionItem("Open Right Side Panel", { command: "helix.openRightPanel", title: "Open Right Side Panel" }, "layout-sidebar-right"),
      new HelixActionItem("Ask Helix", { command: "helix.ask", title: "Ask Helix" }, "comment-discussion"),
      new HelixActionItem("Open @helix Chat", { command: "helix.openChat", title: "Open @helix Chat" }, "sparkle"),
      new HelixActionItem("Review Workspace", { command: "helix.reviewWorkspace", title: "Review Workspace" }, "search"),
      new HelixActionItem("Explain Current File", { command: "helix.explainFile", title: "Explain Current File" }, "file-code"),
      new HelixActionItem("Fix Selection", { command: "helix.fixSelection", title: "Fix Selection" }, "wand"),
      new HelixActionItem("Rewrite Selection", { command: "helix.rewriteSelection", title: "Rewrite Selection" }, "edit"),
      new HelixActionItem("Learning Status", { command: "helix.learnStatus", title: "Learning Status" }, "graph")
    ];
  }
}

function activeRelativePath() {
  const editor = vscode.window.activeTextEditor;
  return editor ? vscode.workspace.asRelativePath(editor.document.uri) : "";
}

function extractReplacement(text) {
  const match = text.match(/```[a-zA-Z0-9_-]*\s*\n([\s\S]*?)\n```/);
  return (match ? match[1] : text).replace(/\r?\n$/, "");
}

async function askCommand() {
  const prompt = await vscode.window.showInputBox({ prompt: "Ask Helix" });
  if (!prompt) {
    return;
  }
  const channel = outputChannel();
  channel.show(true);
  channel.appendLine("> " + prompt);
  try {
    const result = await runHelix(["ask", prompt]);
    channel.appendLine(result);
  } catch (error) {
    vscode.window.showErrorMessage(error.message);
  }
}

async function fixSelectionCommand() {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    vscode.window.showInformationMessage("Open a file and select code for Helix to fix.");
    return;
  }
  const selection = editor.selection;
  const selected = editor.document.getText(selection);
  if (!selected) {
    vscode.window.showInformationMessage("Select code first.");
    return;
  }
  const request = await vscode.window.showInputBox({ prompt: "What should Helix fix?" });
  if (!request) {
    return;
  }
  const prompt = [
    request,
    "",
    "File: " + vscode.workspace.asRelativePath(editor.document.uri),
    "",
    "Selected code:",
    "```",
    selected,
    "```"
  ].join("\n");
  const channel = outputChannel();
  channel.show(true);
  channel.appendLine("Running Helix agent on selection...");
  try {
    const result = await runHelix(["agent", prompt]);
    channel.appendLine(result);
  } catch (error) {
    vscode.window.showErrorMessage(error.message);
  }
}

async function rewriteSelectionCommand() {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    vscode.window.showInformationMessage("Open a file and select code for Helix to rewrite.");
    return;
  }
  const selection = editor.selection;
  const selected = editor.document.getText(selection);
  if (!selected) {
    vscode.window.showInformationMessage("Select code first.");
    return;
  }
  const instruction = await vscode.window.showInputBox({ prompt: "How should Helix rewrite this selection?" });
  if (!instruction) {
    return;
  }
  const prompt = [
    "Rewrite the selected code according to the instruction.",
    "Return only the replacement text. Do not include markdown fences or explanation.",
    "",
    "Instruction: " + instruction,
    "File: " + vscode.workspace.asRelativePath(editor.document.uri),
    "",
    "Selected code:",
    selected
  ].join("\n");
  try {
    const result = extractReplacement(await runHelix(["ask", prompt]));
    const action = await vscode.window.showWarningMessage("Replace the selected text with Helix's rewrite?", "Replace", "Cancel");
    if (action !== "Replace") {
      return;
    }
    await editor.edit(builder => builder.replace(selection, result));
  } catch (error) {
    vscode.window.showErrorMessage(error.message);
  }
}

async function reviewWorkspaceCommand() {
  const channel = outputChannel();
  channel.show(true);
  channel.appendLine("Running Helix workspace review...");
  try {
    const result = await runHelix(["code", "review"]);
    channel.appendLine(result);
  } catch (error) {
    vscode.window.showErrorMessage(error.message);
  }
}

async function explainFileCommand() {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    vscode.window.showInformationMessage("Open a file for Helix to explain.");
    return;
  }
  const path = vscode.workspace.asRelativePath(editor.document.uri);
  const channel = outputChannel();
  channel.show(true);
  channel.appendLine("Explaining " + path + "...");
  try {
    const result = await runHelix(["code", "explain", path]);
    channel.appendLine(result);
  } catch (error) {
    vscode.window.showErrorMessage(error.message);
  }
}

async function learnStatusCommand() {
  try {
    const result = await runHelix(["learn", "status"]);
    vscode.window.showInformationMessage("Helix learning status loaded.");
    const doc = await vscode.workspace.openTextDocument({ content: result, language: "json" });
    await vscode.window.showTextDocument(doc, { preview: true });
  } catch (error) {
    vscode.window.showErrorMessage(error.message);
  }
}

async function openChatCommand() {
  try {
    await vscode.commands.executeCommand("workbench.action.chat.open", "@helix ");
  } catch (_error) {
    await askCommand();
  }
}

function rightPanelHtml(webview) {
  const scriptNonce = nonce();
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource} 'unsafe-inline'; script-src 'nonce-${scriptNonce}';">
  <title>Helix Agent</title>
  <style>
    body {
      font-family: var(--vscode-font-family);
      color: var(--vscode-foreground);
      background: var(--vscode-editor-background);
      margin: 0;
      padding: 14px;
    }
    .header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      margin-bottom: 12px;
    }
    .title {
      font-size: 15px;
      font-weight: 700;
    }
    .status {
      color: var(--vscode-descriptionForeground);
      font-size: 12px;
    }
    textarea {
      box-sizing: border-box;
      width: 100%;
      min-height: 120px;
      resize: vertical;
      color: var(--vscode-input-foreground);
      background: var(--vscode-input-background);
      border: 1px solid var(--vscode-input-border);
      border-radius: 4px;
      padding: 10px;
      font-family: var(--vscode-editor-font-family);
    }
    .toolbar {
      display: flex;
      gap: 6px;
      margin-bottom: 10px;
    }
    select {
      flex: 1;
      min-width: 0;
      color: var(--vscode-dropdown-foreground);
      background: var(--vscode-dropdown-background);
      border: 1px solid var(--vscode-dropdown-border);
      border-radius: 4px;
      padding: 7px;
    }
    .actions {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
      margin: 10px 0;
    }
    button {
      border: 0;
      border-radius: 4px;
      padding: 8px;
      color: var(--vscode-button-foreground);
      background: var(--vscode-button-background);
      cursor: pointer;
      font-size: 12px;
    }
    button.secondary {
      color: var(--vscode-button-secondaryForeground);
      background: var(--vscode-button-secondaryBackground);
    }
    pre {
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      min-height: 180px;
      padding: 10px;
      border: 1px solid var(--vscode-panel-border);
      border-radius: 4px;
      background: var(--vscode-textCodeBlock-background);
      font-family: var(--vscode-editor-font-family);
      font-size: 12px;
      line-height: 1.45;
    }
  </style>
</head>
<body>
  <div class="header">
    <div class="title">Helix Agent</div>
    <div class="status" id="status">Ready</div>
  </div>
  <div class="toolbar">
    <select id="command">
      <optgroup label="Core">
        <option value="ask">Ask</option>
        <option value="agent">Agent Run</option>
        <option value="chat">Open @helix Chat</option>
        <option value="capabilities">Capabilities</option>
        <option value="doctor">Doctor</option>
      </optgroup>
      <optgroup label="Code">
        <option value="review">Review Workspace</option>
        <option value="map">Map Workspace</option>
        <option value="tests">Infer Tests</option>
        <option value="explain">Explain Active File</option>
        <option value="fix">Fix Task</option>
      </optgroup>
      <optgroup label="Context">
        <option value="context">Workspace Context</option>
        <option value="skills">Skills List</option>
        <option value="skillsSearch">Skills Search</option>
        <option value="tools">Tools List</option>
        <option value="providers">Providers</option>
      </optgroup>
      <optgroup label="State">
        <option value="memory">Memory List</option>
        <option value="memorySearch">Memory Search</option>
        <option value="learn">Learning Status</option>
        <option value="sessions">Sessions</option>
        <option value="missions">Missions</option>
        <option value="schedule">Schedule</option>
        <option value="history">History</option>
      </optgroup>
      <optgroup label="Extensions">
        <option value="plugins">Plugins</option>
        <option value="pluginTools">Plugin Tools</option>
        <option value="finetunePrepare">Fine-tune Prepare</option>
        <option value="finetuneAutoDryRun">Fine-tune Auto Dry Run</option>
        <option value="raw">Raw Helix CLI Args</option>
      </optgroup>
    </select>
    <button data-run-selected="true">Run</button>
  </div>
  <textarea id="prompt" placeholder="Ask Helix about this workspace..."></textarea>
  <div class="actions">
    <button data-command="ask">Ask</button>
    <button data-command="agent">Agent Run</button>
    <button data-command="review">Review Workspace</button>
    <button class="secondary" data-command="map">Map Workspace</button>
    <button class="secondary" data-command="tests">Infer Tests</button>
    <button class="secondary" data-command="explain">Explain File</button>
    <button class="secondary" data-command="skills">Skills</button>
    <button class="secondary" data-command="memory">Memory</button>
    <button class="secondary" data-command="learn">Learning Status</button>
    <button class="secondary" data-command="doctor">Doctor</button>
  </div>
  <pre id="output">Helix output will appear here.</pre>
  <script nonce="${scriptNonce}">
    const vscode = acquireVsCodeApi();
    const prompt = document.getElementById("prompt");
    const command = document.getElementById("command");
    const output = document.getElementById("output");
    const status = document.getElementById("status");
    function run(commandName) {
      status.textContent = "Running...";
      output.textContent = "Running Helix...";
      vscode.postMessage({ command: commandName, prompt: prompt.value });
    }
    document.querySelectorAll("button[data-command]").forEach(button => {
      button.addEventListener("click", () => {
        run(button.dataset.command);
      });
    });
    document.querySelector("button[data-run-selected]").addEventListener("click", () => run(command.value));
    window.addEventListener("message", event => {
      const message = event.data;
      status.textContent = message.ok ? "Ready" : "Error";
      output.textContent = message.text || "";
    });
  </script>
</body>
</html>`;
}

async function runRightPanelCommand(panel, message) {
  const command = message.command;
  const prompt = message.prompt || "";
  let args;
  if (command === "review") {
    args = ["code", "review"];
  } else if (command === "agent") {
    args = ["agent", prompt || "Inspect this workspace and suggest next steps."];
  } else if (command === "map") {
    args = ["code", "map"];
  } else if (command === "tests") {
    args = ["code", "tests"];
  } else if (command === "explain") {
    const path = activeRelativePath();
    args = path ? ["code", "explain", path] : ["ask", "Explain the current workspace."];
  } else if (command === "learn") {
    args = ["learn", "status"];
  } else if (command === "fix") {
    args = ["code", "fix", prompt || "Plan a safe code improvement."];
  } else if (command === "context") {
    args = ["context", "show"];
  } else if (command === "skills") {
    args = ["skills", "list"];
  } else if (command === "skillsSearch") {
    args = ["skills", "search", prompt || "code"];
  } else if (command === "tools") {
    args = ["tools", "list"];
  } else if (command === "providers") {
    args = ["providers", "list"];
  } else if (command === "memory") {
    args = ["memory", "list"];
  } else if (command === "memorySearch") {
    args = ["memory", "search", prompt || ""];
  } else if (command === "sessions") {
    args = ["sessions", "list"];
  } else if (command === "missions") {
    args = ["mission", "list"];
  } else if (command === "schedule") {
    args = ["schedule", "list"];
  } else if (command === "history") {
    args = ["history"];
  } else if (command === "plugins") {
    args = ["plugins", "list"];
  } else if (command === "pluginTools") {
    args = ["plugins", "tools"];
  } else if (command === "capabilities") {
    args = ["capabilities"];
  } else if (command === "doctor") {
    args = ["doctor"];
  } else if (command === "finetunePrepare") {
    args = ["finetune", "prepare", "--min-rating", "4"];
  } else if (command === "finetuneAutoDryRun") {
    args = ["finetune", "auto", "--base-model", prompt || "gpt-4.1-mini", "--dry-run"];
  } else if (command === "chat") {
    await openChatCommand();
    panel.webview.postMessage({ ok: true, text: "Opened @helix Chat." });
    return;
  } else if (command === "raw") {
    args = splitArgs(prompt || "capabilities");
  } else {
    args = ["ask", prompt || "Summarize this workspace."];
  }
  try {
    const text = await runHelix(args);
    panel.webview.postMessage({ ok: true, text });
  } catch (error) {
    panel.webview.postMessage({ ok: false, text: error.message });
  }
}

function splitArgs(text) {
  const matches = String(text).match(/"([^"\\]*(?:\\.[^"\\]*)*)"|'([^'\\]*(?:\\.[^'\\]*)*)'|\S+/g) || [];
  return matches.map(part => {
    if ((part.startsWith('"') && part.endsWith('"')) || (part.startsWith("'") && part.endsWith("'"))) {
      return part.slice(1, -1);
    }
    return part;
  });
}

function openRightPanelCommand() {
  if (rightPanel) {
    rightPanel.reveal(vscode.ViewColumn.Beside);
    return;
  }
  rightPanel = vscode.window.createWebviewPanel(
    "helixRightPanel",
    "Helix Agent",
    vscode.ViewColumn.Beside,
    {
      enableScripts: true,
      retainContextWhenHidden: true
    }
  );
  rightPanel.iconPath = new vscode.ThemeIcon("sparkle");
  rightPanel.webview.html = rightPanelHtml(rightPanel.webview);
  rightPanel.webview.onDidReceiveMessage(message => runRightPanelCommand(rightPanel, message));
  rightPanel.onDidDispose(() => {
    rightPanel = undefined;
  });
}

function registerChat(context) {
  if (!vscode.chat || !vscode.chat.createChatParticipant) {
    return;
  }
  const participant = vscode.chat.createChatParticipant("helix.agent", async (request, _context, stream, token) => {
    stream.markdown("Thinking with Helix...\n\n");
    try {
      let result;
      if (request.command === "map") {
        result = await runHelix(["code", "map"]);
      } else if (request.command === "review") {
        result = await runHelix(["code", "review"]);
      } else if (request.command === "explain") {
        const path = activeRelativePath();
        result = path ? await runHelix(["code", "explain", path]) : await runHelix(["ask", request.prompt || "Explain the current workspace."]);
      } else if (request.command === "fix") {
        result = await runHelix(["code", "fix", request.prompt || "Plan a safe code improvement."]);
      } else if (request.command === "learn") {
        result = await runHelix(["learn", "status"]);
      } else {
        result = await runHelix(["ask", request.prompt]);
      }
      if (!token.isCancellationRequested) {
        stream.markdown(result || "Helix returned no content.");
      }
    } catch (error) {
      stream.markdown("Helix error: `" + error.message.replace(/`/g, "'") + "`");
    }
  });
  participant.iconPath = new vscode.ThemeIcon("sparkle");
  context.subscriptions.push(participant);
}

class HelixWorkspaceTool {
  async prepareInvocation(options) {
    const request = options.input && options.input.request ? options.input.request : "workspace context";
    return {
      invocationMessage: "Running Helix Agent",
      confirmationMessages: {
        title: "Run Helix Agent",
        message: new vscode.MarkdownString("Run local `helix` for: `" + String(request).replace(/`/g, "'") + "`")
      }
    };
  }

  async invoke(options) {
    const input = options.input || {};
    const mode = input.mode || "ask";
    let result;
    if (mode === "map") {
      result = await runHelix(["code", "map"]);
    } else if (mode === "tests") {
      result = await runHelix(["code", "tests"]);
    } else {
      result = await runHelix(["ask", input.request || "Summarize this workspace."]);
    }
    return new vscode.LanguageModelToolResult([new vscode.LanguageModelTextPart(result)]);
  }
}

function registerLanguageModelTools(context) {
  if (!vscode.lm || !vscode.lm.registerTool || !vscode.LanguageModelToolResult) {
    return;
  }
  context.subscriptions.push(vscode.lm.registerTool("helix_workspace", new HelixWorkspaceTool()));
}

function activate(context) {
  const panelProvider = new HelixPanelProvider();
  context.subscriptions.push(vscode.window.registerTreeDataProvider("helix.panel", panelProvider));
  context.subscriptions.push(vscode.commands.registerCommand("helix.ask", askCommand));
  context.subscriptions.push(vscode.commands.registerCommand("helix.fixSelection", fixSelectionCommand));
  context.subscriptions.push(vscode.commands.registerCommand("helix.rewriteSelection", rewriteSelectionCommand));
  context.subscriptions.push(vscode.commands.registerCommand("helix.reviewWorkspace", reviewWorkspaceCommand));
  context.subscriptions.push(vscode.commands.registerCommand("helix.explainFile", explainFileCommand));
  context.subscriptions.push(vscode.commands.registerCommand("helix.learnStatus", learnStatusCommand));
  context.subscriptions.push(vscode.commands.registerCommand("helix.openChat", openChatCommand));
  context.subscriptions.push(vscode.commands.registerCommand("helix.openRightPanel", openRightPanelCommand));
  registerChat(context);
  registerLanguageModelTools(context);
}

function deactivate() {}

module.exports = { activate, deactivate };
