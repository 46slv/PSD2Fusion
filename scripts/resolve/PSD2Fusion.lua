-- PSD2Fusion Resolve/Fusion launcher.
--
-- This is deliberately a thin Comp script.  The parser/compiler stays in the
-- repository; the installer replaces the three tokens below with the local
-- repository, Python, and bridge paths.

local PSD2FUSION_REPO = [[__PSD2FUSION_REPO__]]
local PSD2FUSION_PYTHON = [[__PSD2FUSION_PYTHON__]]
local PSD2FUSION_BRIDGE = [[__PSD2FUSION_BRIDGE__]]

local function safe_text(value)
    if value == nil then
        return ""
    end
    local ok, result = pcall(function()
        return tostring(value)
    end)
    if ok then
        return result
    end
    return "<unprintable>"
end

local function bool_text(value)
    if value then
        return "yes"
    end
    return "no"
end

local function trim_detail(value, limit)
    local text = safe_text(value)
    local maximum = limit or 1400
    if text == "" then
        return "(none)"
    end
    if string.len(text) > maximum then
        return string.sub(text, string.len(text) - maximum + 1)
    end
    return text
end

local function map_path(path, fusion_app)
    if path == nil or path == "" then
        return nil
    end
    if fusion_app ~= nil and fusion_app.MapPath ~= nil then
        local ok, mapped = pcall(function()
            return fusion_app:MapPath(path)
        end)
        if ok and mapped ~= nil and mapped ~= "" then
            return mapped
        end
    end
    return path
end

local function file_exists(path)
    if path == nil or path == "" then
        return false
    end
    if bmd ~= nil and bmd.fileexists ~= nil then
        local ok, result = pcall(function()
            return bmd.fileexists(path)
        end)
        if ok and result then
            return true
        end
    end
    local handle = io.open(path, "rb")
    if handle ~= nil then
        handle:close()
        return true
    end
    return false
end

local function read_file(path)
    local handle = io.open(path, "rb")
    if handle == nil then
        return ""
    end
    local contents = handle:read("*a") or ""
    handle:close()
    return contents
end

local function path_join(base, leaf, separator)
    local trimmed = string.gsub(base or "", "[\\/]+$", "")
    if trimmed == "" then
        return leaf
    end
    return trimmed .. separator .. leaf
end

local function path_dirname(path)
    local parent = string.match(path or "", "^(.*)[\\/][^\\/]+$")
    return parent or "."
end

local function path_filename(path)
    return string.match(path or "", "([^\\/]+)$") or ""
end

local function path_stem(path)
    local filename = path_filename(path)
    local stem = string.gsub(filename, "%.[^%.]*$", "")
    if stem == "" then
        return "PSD2Fusion"
    end
    return stem
end

local function json_escape(value)
    local text = safe_text(value)
    text = string.gsub(text, "\\", "\\\\")
    text = string.gsub(text, '"', '\\"')
    text = string.gsub(text, "\r", "\\r")
    text = string.gsub(text, "\n", "\\n")
    text = string.gsub(text, "\t", "\\t")
    return text
end

local function write_request(path, source_path, output_path, force)
    local handle, open_error = io.open(path, "wb")
    if handle == nil then
        return false, open_error or "Could not open the bridge request file."
    end
    local payload = '{"psd":"' .. json_escape(source_path)
        .. '","output":"' .. json_escape(output_path)
        .. '","force":' .. (force and "true" or "false") .. "}\n"
    local written, write_error = handle:write(payload)
    handle:close()
    if written == nil then
        return false, write_error or "Could not write the bridge request file."
    end
    return true, nil
end

local function shell_quote(value, windows)
    local text = safe_text(value)
    if windows then
        text = string.gsub(text, '"', '\\"')
        return '"' .. text .. '"'
    end
    text = string.gsub(text, "'", "'\\''")
    return "'" .. text .. "'"
end

local function truthy(value)
    return value == true or value == 1 or value == "1" or value == "true"
end

local function directory_exists(path)
    if path == nil or path == "" then
        return false
    end
    if bmd ~= nil and bmd.direxists ~= nil then
        local ok, result = pcall(function()
            return bmd.direxists(path)
        end)
        if ok and result then
            return true
        end
    end
    -- Lua has no portable directory predicate.  On Windows, os.rename of a
    -- directory onto itself is a read-only existence probe; error 5/13 still
    -- means that the path exists but cannot be renamed.
    local ok, _, code = os.rename(path, path)
    return ok == true or code == 5 or code == 13
end

local function artifact_state(output_path, separator)
    local composition_path = path_join(output_path, "PSD2Fusion.comp", separator)
    local manifest_path = path_join(output_path, "manifest.json", separator)
    local assets_path = path_join(output_path, "assets", separator)
    local result = {
        composition = file_exists(composition_path),
        manifest = file_exists(manifest_path),
        assets = directory_exists(assets_path),
    }
    result.any = result.composition or result.manifest or result.assets
    result.complete = result.composition and result.manifest and result.assets
    return result
end

local function artifact_detail(artifacts)
    local state = artifacts or {}
    return "comp=" .. bool_text(state.composition)
        .. ", manifest=" .. bool_text(state.manifest)
        .. ", assets=" .. bool_text(state.assets)
end

local function process_exit_code(first, second, third)
    if type(first) == "number" then
        return first
    end
    if type(third) == "number" then
        return third
    end
    return nil
end

local function comp_name(comp_object)
    if comp_object == nil then
        return ""
    end
    local ok, name = pcall(function()
        if comp_object.GetAttrs == nil then
            return nil
        end
        local attrs = comp_object:GetAttrs()
        if attrs == nil then
            return nil
        end
        return attrs.COMPN_Name or attrs.Name
    end)
    if ok and name ~= nil then
        return safe_text(name)
    end
    return ""
end

local function resolve_comp_state()
    local selected = nil
    local selected_origin = "none"
    if composition ~= nil then
        selected = composition
        selected_origin = "composition"
    elseif comp ~= nil then
        selected = comp
        selected_origin = "comp"
    end

    local current = nil
    local current_origin = "fu:GetCurrentComp() unavailable"
    local current_error = ""
    local getter_ok, getter = pcall(function()
        return fu ~= nil and fu.GetCurrentComp
    end)
    if getter_ok and getter ~= nil then
        local call_ok, result = pcall(function()
            return fu:GetCurrentComp()
        end)
        if call_ok then
            current = result
            current_origin = "fu:GetCurrentComp()"
        else
            current_error = safe_text(result)
            current_origin = "fu:GetCurrentComp() error"
        end
    end

    if selected == nil and current ~= nil then
        selected = current
        selected_origin = current_origin
    end

    local same = false
    local same_ok, same_result = pcall(function()
        return selected ~= nil and current ~= nil and selected == current
    end)
    if same_ok then
        same = same_result
    end
    return {
        selected = selected,
        selected_origin = selected_origin,
        selected_name = comp_name(selected),
        current = current,
        current_origin = current_origin,
        current_name = comp_name(current),
        current_error = current_error,
        same = same,
    }
end

local function snapshot_tools(target_comp)
    if target_comp == nil or target_comp.GetToolList == nil then
        return nil, "Current Composition does not expose GetToolList."
    end
    local ok, tools = pcall(function()
        return target_comp:GetToolList(false)
    end)
    if not ok then
        return nil, safe_text(tools)
    end
    if tools == nil then
        return nil, "GetToolList returned nil."
    end
    local references = {}
    local count = 0
    for _, tool in pairs(tools) do
        references[tool] = true
        count = count + 1
    end
    return {count = count, references = references}, nil
end

local function original_tools_preserved(before, after)
    if before == nil or after == nil then
        return false
    end
    for tool, _ in pairs(before.references) do
        if not after.references[tool] then
            return false
        end
    end
    return true
end

local function settings_have_tools(settings)
    if type(settings) ~= "table" or type(settings.Tools) ~= "table" then
        return false
    end
    for _, _ in pairs(settings.Tools) do
        return true
    end
    return false
end

local function insert_generated_graph(target_comp, composition_path)
    if bmd == nil or bmd.readfile == nil then
        return false, "Fusion bmd.readfile API is unavailable."
    end
    local required = {"Paste", "GetToolList", "Lock", "Unlock", "StartUndo", "EndUndo", "Undo"}
    for _, method_name in ipairs(required) do
        local method_ok, method = pcall(function()
            return target_comp[method_name]
        end)
        if not method_ok or method == nil then
            return false, "Current Composition does not expose " .. method_name .. "."
        end
    end

    local read_ok, settings = pcall(function()
        return bmd.readfile(composition_path)
    end)
    if not read_ok then
        return false, "Could not read generated Fusion settings: " .. safe_text(settings)
    end
    if not settings_have_tools(settings) then
        return false, "Generated Fusion settings did not contain a non-empty Tools table."
    end

    local identity_before = resolve_comp_state()
    if identity_before.current == nil or identity_before.current ~= target_comp then
        return false, "Current Fusion Composition changed before insertion; no graph was inserted."
    end
    local before, before_error = snapshot_tools(target_comp)
    if before == nil then
        return false, "Could not snapshot current Composition before insertion: " .. safe_text(before_error)
    end

    local locked = false
    local undo_started = false
    local paste_result = nil
    local after = nil
    local failure_detail = nil
    local operation_ok, operation_error = xpcall(function()
        target_comp:Lock()
        locked = true

        local locked_identity = resolve_comp_state()
        if locked_identity.current == nil or locked_identity.current ~= target_comp then
            error("Current Fusion Composition changed before the locked insertion.")
        end

        target_comp:StartUndo("PSD2Fusion insert generated graph")
        undo_started = true
        paste_result = target_comp:Paste(settings)
        local after_error = nil
        after, after_error = snapshot_tools(target_comp)
        if after == nil then
            error("Could not snapshot current Composition after insertion: " .. safe_text(after_error))
        end

        local identity_after = resolve_comp_state()
        local grew = after.count > before.count
        local preserved = original_tools_preserved(before, after)
        local same_identity = identity_after.current ~= nil and identity_after.current == target_comp
        local paste_succeeded = paste_result ~= false and paste_result ~= nil
        local changed = after.count ~= before.count or not preserved

        target_comp:EndUndo(changed)
        undo_started = false

        if not paste_succeeded then
            error("Fusion Paste returned " .. safe_text(paste_result) .. ".")
        end
        if not same_identity then
            error("Current Fusion Composition changed during insertion.")
        end
        if not grew then
            error("Fusion Paste did not add any tools.")
        end
        if not preserved then
            error("An existing tool was not preserved during insertion.")
        end
    end, function(err)
        return safe_text(err)
    end)

    if not operation_ok then
        failure_detail = safe_text(operation_error)
        local rollback_before = after
        if rollback_before == nil then
            rollback_before = select(1, snapshot_tools(target_comp))
        end
        local changed = rollback_before ~= nil
            and (rollback_before.count ~= before.count or not original_tools_preserved(before, rollback_before))
        if undo_started then
            pcall(function()
                target_comp:EndUndo(changed)
            end)
            undo_started = false
        end
        if changed then
            local undo_ok, undo_error = pcall(function()
                target_comp:Undo()
            end)
            local rolled_back = select(1, snapshot_tools(target_comp))
            local rollback_verified = undo_ok
                and rolled_back ~= nil
                and rolled_back.count == before.count
                and original_tools_preserved(before, rolled_back)
            if not rollback_verified then
                failure_detail = failure_detail .. " Rollback verification failed: " .. safe_text(undo_error)
            else
                failure_detail = failure_detail .. " Partial insertion was rolled back."
            end
        end
    end

    if locked then
        local unlock_ok, unlock_error = pcall(function()
            target_comp:Unlock()
        end)
        if not unlock_ok then
            return false, (failure_detail or "Insertion completed but unlock failed.")
                .. " Unlock error: " .. safe_text(unlock_error)
        end
    end

    if not operation_ok then
        return false, failure_detail
    end
    return true, "inserted " .. tostring(after.count - before.count) .. " tools into the current Composition"
end

local function show_message(target_comp, title, body)
    if target_comp ~= nil and target_comp.AskUser ~= nil then
        local ok = pcall(function()
            target_comp:AskUser(title, {
                {"message", Name = "Status", "Text", Default = body, ReadOnly = true, Wrap = true, Lines = 8}
            })
        end)
        if ok then
            return
        end
    end
    print("PSD2Fusion: " .. safe_text(body))
end

local function failure_body(state, detail)
    local current_comp = bool_text(state.current_comp_resolved)
    local current_origin = safe_text(state.current_comp_origin or "unknown")
    local current_name = safe_text(state.current_comp_name or "")
    local bridge_exit = state.bridge_exit_code
    if bridge_exit == nil then
        bridge_exit = "unknown"
    end
    local artifacts = state.artifacts or {}
    local lines = {
        "PSD2Fusion failed.",
        "",
        "phase: " .. safe_text(state.phase or "unknown"),
        "input PSD: " .. safe_text(state.input_psd or "(not selected)"),
        "output directory: " .. safe_text(state.output_dir or "(not determined)"),
        "bridge exit code: " .. safe_text(bridge_exit),
        "stderr / exception summary: " .. trim_detail(detail or state.stderr, 1050),
        "artifact exists: " .. bool_text(artifacts.complete),
        "artifact detail: " .. artifact_detail(artifacts),
        "current comp resolved: " .. current_comp .. " (" .. current_origin .. ")",
    }
    if current_name ~= "" then
        table.insert(lines, "current comp name: " .. current_name)
    end
    if state.current_comp_api_resolved ~= nil then
        table.insert(lines, "fu:GetCurrentComp(): " .. bool_text(state.current_comp_api_resolved))
    end
    if state.comp_match ~= nil and state.current_comp_api_resolved then
        table.insert(lines, "selected/current object match: " .. bool_text(state.comp_match))
    end
    if state.insert_error ~= nil and state.insert_error ~= "" then
        table.insert(lines, "Insertion error: " .. trim_detail(state.insert_error, 700))
    end
    return table.concat(lines, "\n")
end

local function show_failure(target_comp, state, detail)
    show_message(target_comp, "PSD2Fusion failed", failure_body(state, detail))
end

local function ask_overwrite(target_comp, output_path)
    if target_comp == nil or target_comp.AskUser == nil then
        return false, false
    end
    local ok, response = pcall(function()
        return target_comp:AskUser("PSD2Fusion output exists", {
            {"overwrite", Name = "Allow --force for this run", "Checkbox", Default = false},
            {"details", Name = "Output", "Text", Default = "The output already contains a PSD2Fusion result:\n" .. output_path .. "\n\nEnable the checkbox only when replacing that generated result is intended.", ReadOnly = true, Wrap = true, Lines = 6}
        })
    end)
    if not ok or response == nil then
        return false, true
    end
    return truthy(response.overwrite), false
end

local function execute_converter(source_path, output_path, force, separator)
    local windows = (package.config ~= nil and string.sub(package.config, 1, 1) == "\\") or FuPLATFORM_WINDOWS
    local evidence = {
        phase = "bridge_request",
        input_psd = source_path,
        output_dir = output_path,
        bridge_exit_code = nil,
        artifacts = artifact_state(output_path, separator),
    }
    local log_path = os.tmpname()
    local request_path = os.tmpname()
    if log_path == nil or log_path == "" or request_path == nil or request_path == "" then
        evidence.stderr = "Could not allocate temporary bridge files."
        return false, evidence.stderr, evidence
    end
    -- os.tmpname() may create the files; remove them before writing/redirection.
    pcall(function() os.remove(log_path) end)
    pcall(function() os.remove(request_path) end)

    local request_ok, request_error = write_request(request_path, source_path, output_path, force)
    if not request_ok then
        evidence.stderr = safe_text(request_error)
        pcall(function() os.remove(log_path) end)
        pcall(function() os.remove(request_path) end)
        return false, evidence.stderr, evidence
    end

    -- Only installer-owned executable/bridge/temp paths cross the shell.  The
    -- user PSD and output paths are UTF-8 JSON in request_path, so cmd.exe does
    -- not parse them and no codepage conversion is involved.
    local command = shell_quote(PSD2FUSION_PYTHON, windows)
        .. " " .. shell_quote(PSD2FUSION_BRIDGE, windows)
        .. " --request " .. shell_quote(request_path, windows)
        .. " > " .. shell_quote(log_path, windows) .. " 2>&1"
    if windows then
        -- Lua's Windows os.execute invokes cmd.exe with quoting rules that
        -- differ from an interactive prompt.  Keep the wrapper for reliable
        -- completion/exit status; only ASCII launcher/temp paths cross it.
        command = "cmd.exe /d /s /c \"" .. command .. "\""
    end
    evidence.phase = "bridge_launch"

    local process_call_ok, first, second, third = pcall(function()
        return os.execute(command)
    end)
    local log_text = read_file(log_path)
    pcall(function() os.remove(log_path) end)
    pcall(function() os.remove(request_path) end)
    evidence.stderr = trim_detail(log_text, 1400)
    if not process_call_ok then
        evidence.stderr = safe_text(first)
        evidence.phase = "bridge_launch"
        evidence.artifacts = artifact_state(output_path, separator)
        return false, evidence.stderr, evidence
    end

    evidence.bridge_exit_code = process_exit_code(first, second, third)
    local process_ok = first == true
        or (type(first) == "number" and first == 0)
        or (type(third) == "number" and third == 0)
    evidence.artifacts = artifact_state(output_path, separator)
    if process_ok and evidence.artifacts.complete then
        evidence.phase = "converter_complete"
        return true, log_text, evidence
    end

    if process_ok then
        evidence.phase = "artifact_check"
    else
        evidence.phase = "converter_failed"
    end
    local detail = log_text
    if detail == nil or detail == "" then
        detail = "bridge process did not complete successfully (exit code: "
            .. safe_text(evidence.bridge_exit_code) .. "; " .. artifact_detail(evidence.artifacts) .. ")."
    end
    return false, trim_detail(detail, 1400), evidence
end

local function main(state)
    state.phase = "composition_resolution"
    local fusion_app = fusion or app
    local comp_state = resolve_comp_state()
    local target_comp = comp_state.selected
    state.target_comp = target_comp
    state.current_comp_resolved = target_comp ~= nil
    state.current_comp_origin = comp_state.selected_origin
    state.current_comp_name = comp_state.selected_name
    state.current_comp_api_resolved = comp_state.current ~= nil
    state.comp_match = comp_state.same

    if fusion_app == nil then
        state.phase = "fusion_context"
        show_failure(target_comp, state, "Fusion scripting context is unavailable. Open the Fusion page and run the Comp script again.")
        return
    end
    if target_comp == nil then
        state.phase = "composition_resolution"
        show_failure(target_comp, state, "No current Fusion Composition was resolved. Select a Fusion Composition, then run the Comp script again.")
        return
    end
    if string.find(PSD2FUSION_PYTHON, "__PSD2FUSION_", 1, true) ~= nil
        or string.find(PSD2FUSION_BRIDGE, "__PSD2FUSION_", 1, true) ~= nil then
        state.phase = "launcher_installation"
        show_failure(target_comp, state, "The launcher is not installed yet. Run scripts\\install_resolve.ps1 from the PSD2Fusion repository.")
        return
    end

    local separator = (package.config ~= nil and string.sub(package.config, 1, 1)) or "\\"
    local last_dir = nil
    if fusion_app.GetData ~= nil then
        local ok, remembered = pcall(function()
            return fusion_app:GetData("PSD2Fusion.LastSourceDir")
        end)
        if ok and remembered ~= nil and remembered ~= "" then
            last_dir = remembered
        end
    end

    state.phase = "picker"
    local ok_file, selected = pcall(function()
        return fusion_app:RequestFile(last_dir or "")
    end)
    if not ok_file then
        show_failure(target_comp, state, safe_text(selected))
        return
    end
    if selected == nil or selected == "" then
        return
    end

    state.phase = "selected_path"
    local map_ok, source_path = pcall(function()
        return map_path(selected, fusion_app)
    end)
    if not map_ok then
        state.input_psd = safe_text(selected)
        show_failure(target_comp, state, safe_text(source_path))
        return
    end
    state.input_psd = safe_text(source_path or selected)
    if source_path == nil or not file_exists(source_path) then
        show_failure(target_comp, state, "The selected PSD could not be read:\n" .. state.input_psd)
        return
    end
    local lower_source = string.lower(source_path)
    if string.sub(lower_source, -4) ~= ".psd" then
        show_failure(target_comp, state, "Please select a Photoshop PSD file.\nSelected: " .. source_path)
        return
    end

    local source_dir = path_dirname(source_path)
    if fusion_app.SetData ~= nil then
        pcall(function()
            fusion_app:SetData("PSD2Fusion.LastSourceDir", source_dir)
        end)
    end
    local output_path = path_join(source_dir, path_stem(source_path) .. "_fusion", separator)
    state.output_dir = output_path
    local composition_path = path_join(output_path, "PSD2Fusion.comp", separator)
    local manifest_path = path_join(output_path, "manifest.json", separator)
    local force = false
    if file_exists(composition_path) or file_exists(manifest_path) then
        state.phase = "overwrite_guard"
        local allow_force, cancelled = ask_overwrite(target_comp, output_path)
        if cancelled then
            show_message(target_comp, "PSD2Fusion", "Conversion cancelled. Existing output was left untouched:\n" .. output_path)
            return
        end
        if not allow_force then
            show_message(target_comp, "PSD2Fusion", "Conversion cancelled. Enable --force in the overwrite dialog to replace this generated output:\n" .. output_path)
            return
        end
        force = true
    end

    if target_comp ~= nil and target_comp.Print ~= nil then
        pcall(function()
            target_comp:Print("PSD2Fusion: converting " .. source_path .. " -> " .. output_path .. "\n")
        end)
    end
    state.phase = "bridge_launch"
    local converted, detail, evidence = execute_converter(source_path, output_path, force, separator)
    state.phase = evidence.phase
    state.bridge_exit_code = evidence.bridge_exit_code
    state.stderr = evidence.stderr
    state.artifacts = evidence.artifacts
    if not converted then
        show_failure(target_comp, state, detail)
        return
    end

    state.phase = "graph_insertion"
    local inserted, insert_detail = insert_generated_graph(target_comp, composition_path)
    state.artifacts = artifact_state(output_path, separator)
    if not inserted then
        state.insert_error = insert_detail
        show_failure(target_comp, state, insert_detail)
        return
    end

    state.phase = "success_dialog"
    local body = "PSD2Fusion completed.\n\nComposition: " .. composition_path
        .. "\nAssets: " .. path_join(output_path, "assets", separator)
        .. "\nFusion: " .. insert_detail
        .. "\nCurrent comp: " .. bool_text(state.current_comp_resolved)
        .. " (" .. safe_text(state.current_comp_origin) .. ")"
    show_message(target_comp, "PSD2Fusion", body)
end

local execution = {
    phase = "startup",
    input_psd = "",
    output_dir = "",
    bridge_exit_code = nil,
    stderr = "",
    artifacts = {composition = false, manifest = false, assets = false, complete = false},
    current_comp_resolved = false,
}

local ok, error_message = xpcall(function()
    main(execution)
end, function(err)
    return safe_text(err)
end)
if not ok then
    show_failure(execution.target_comp, execution, error_message)
end
