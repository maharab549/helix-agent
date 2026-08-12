const vscode = require("vscode");
const cp = require("child_process");

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
  context.subscriptions.push(vscode.commands.registerCommand("helix.ask", askCommand));
  context.subscriptions.push(vscode.commands.registerCommand("helix.fixSelection", fixSelectionCommand));
  context.subscriptions.push(vscode.commands.registerCommand("helix.rewriteSelection", rewriteSelectionCommand));
  context.subscriptions.push(vscode.commands.registerCommand("helix.reviewWorkspace", reviewWorkspaceCommand));
  context.subscriptions.push(vscode.commands.registerCommand("helix.explainFile", explainFileCommand));
  context.subscriptions.push(vscode.commands.registerCommand("helix.learnStatus", learnStatusCommand));
  registerChat(context);
  registerLanguageModelTools(context);
}

function deactivate() {}

module.exports = { activate, deactivate };
