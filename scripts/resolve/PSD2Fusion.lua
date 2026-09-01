-- PSD2Fusion Resolve/Fusion launcher.
--
-- This is deliberately a thin Comp script.  The parser/compiler stays in the
-- repository; the installer replaces the three tokens below with the local
-- repository, Python, and bridge paths.

local PSD2FUSION_REPO = [[__PSD2FUSION_REPO__]]
local PSD2FUSION_PYTHON = [[__PSD2FUSION_PYTHON__]]
local PSD2FUSION_BRIDGE = [[__PSD2FUSION_BRIDGE__]]

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

local function shell_quote(value, windows)
    local text = tostring(value or "")
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
    print("PSD2Fusion: " .. tostring(body))
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

local function execute_converter(source_path, output_path, force, fusion_app)
    local windows = (package.config ~= nil and string.sub(package.config, 1, 1) == "\\") or FuPLATFORM_WINDOWS
    local log_path = os.tmpname()
    if log_path == nil or log_path == "" then
        return false, "Could not allocate a temporary log file."
    end
    -- os.tmpname() may create the file; let the shell recreate it with the
    -- requested redirection instead.
    pcall(function()
        os.remove(log_path)
    end)

    local command = shell_quote(PSD2FUSION_PYTHON, windows)
        .. " " .. shell_quote(PSD2FUSION_BRIDGE, windows)
        .. " " .. shell_quote(source_path, windows)
        .. " --output " .. shell_quote(output_path, windows)
    if force then
        command = command .. " --force"
    end
    command = command .. " > " .. shell_quote(log_path, windows) .. " 2>&1"
    if windows then
        -- Lua's Windows os.execute passes an unwrapped quoted executable to
        -- the shell differently than an interactive cmd prompt.  Explicitly
        -- wrap the complete command so paths and arguments survive cmd.exe's
        -- /c parsing.
        command = "cmd.exe /d /s /c \"" .. command .. "\""
    end

    local first, second, third = os.execute(command)
    local process_ok = first == true or first == 0 or third == 0
    local log_text = read_file(log_path)
    pcall(function()
        os.remove(log_path)
    end)

    local composition_path = path_join(output_path, "PSD2Fusion.comp", (windows and "\\" or "/"))
    if process_ok and file_exists(composition_path) then
        return true, log_text
    end
    if log_text == nil or log_text == "" then
        log_text = "The converter did not produce PSD2Fusion.comp (process status: " .. tostring(first) .. ")."
    end
    if string.len(log_text) > 1400 then
        log_text = string.sub(log_text, string.len(log_text) - 1399)
    end
    return false, log_text
end

local function main()
    local fusion_app = fusion or app
    local target_comp = composition or comp
    if target_comp == nil and fu ~= nil and fu.GetCurrentComp ~= nil then
        local ok, current = pcall(function()
            return fu:GetCurrentComp()
        end)
        if ok then
            target_comp = current
        end
    end
    if fusion_app == nil then
        show_message(target_comp, "PSD2Fusion", "Fusion scripting context is unavailable. Open the Fusion page and run the Comp script again.")
        return
    end
    if string.find(PSD2FUSION_PYTHON, "__PSD2FUSION_", 1, true) ~= nil
        or string.find(PSD2FUSION_BRIDGE, "__PSD2FUSION_", 1, true) ~= nil then
        show_message(target_comp, "PSD2Fusion", "The launcher is not installed yet. Run scripts\\install_resolve.ps1 from the PSD2Fusion repository.")
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

    local ok_file, selected = pcall(function()
        return fusion_app:RequestFile(last_dir or "")
    end)
    if not ok_file or selected == nil or selected == "" then
        return
    end
    local source_path = map_path(selected, fusion_app)
    if source_path == nil or not file_exists(source_path) then
        show_message(target_comp, "PSD2Fusion", "The selected PSD could not be read:\n" .. tostring(source_path or selected))
        return
    end
    local lower_source = string.lower(source_path)
    if string.sub(lower_source, -4) ~= ".psd" then
        show_message(target_comp, "PSD2Fusion", "Please select a Photoshop PSD file.\nSelected: " .. source_path)
        return
    end

    local source_dir = path_dirname(source_path)
    if fusion_app.SetData ~= nil then
        pcall(function()
            fusion_app:SetData("PSD2Fusion.LastSourceDir", source_dir)
        end)
    end
    local output_path = path_join(source_dir, path_stem(source_path) .. "_fusion", separator)
    local composition_path = path_join(output_path, "PSD2Fusion.comp", separator)
    local manifest_path = path_join(output_path, "manifest.json", separator)
    local force = false
    if file_exists(composition_path) or file_exists(manifest_path) then
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
    local converted, detail = execute_converter(source_path, output_path, force, fusion_app)
    if not converted then
        show_message(target_comp, "PSD2Fusion failed", "The converter failed.\n\n" .. tostring(detail) .. "\n\nOutput (if partially created):\n" .. output_path)
        return
    end

    local loaded = false
    local recognized = false
    local load_detail = "not attempted"
    if fusion_app.LoadComp ~= nil then
        local load_ok, loaded_comp = pcall(function()
            return fusion_app:LoadComp(composition_path)
        end)
        if load_ok and loaded_comp ~= nil then
            loaded = true
            load_detail = "loaded"
            if loaded_comp.FindTool ~= nil then
                local find_ok, media_out = pcall(function()
                    return loaded_comp:FindTool("MediaOut1")
                end)
                recognized = find_ok and media_out ~= nil
                if recognized then
                    load_detail = "loaded (MediaOut1 recognized)"
                end
            end
        else
            load_detail = "automatic Fusion load was unavailable"
        end
    end

    local body = "PSD2Fusion completed.\n\nComposition: " .. composition_path
        .. "\nAssets: " .. path_join(output_path, "assets", separator)
        .. "\nFusion: " .. load_detail
    if not loaded or not recognized then
        body = body .. "\n\nOpen the .comp from the Fusion page if it did not appear automatically."
    end
    show_message(target_comp, "PSD2Fusion", body)
end

local ok, error_message = xpcall(main, function(err)
    return tostring(err)
end)
if not ok then
    show_message(composition or comp, "PSD2Fusion failed", error_message)
end
