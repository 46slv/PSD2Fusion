-- PARITY-004 bounded Fusion boundary probe.
--
-- The PowerShell runner creates a tab-separated task file from the fixture
-- manifest.  Each line is: case_id, scope, comp_path, output_dir, and a '|'
-- separated list of boundary_label=tool_name entries.  The probe pastes one
-- generated composition into the disposable current composition, writes a
-- Saver frame-0 artifact for each named tool, and undoes the paste/Savers.
-- It never evaluates a formula oracle or decides which pixels are correct.

local task_path = arg and arg[1]
local records_path = arg and arg[2]
assert(task_path and records_path, "usage: parity004_boundary_probe.lua <tasks.tsv> <records.tsv>")

local function text(value)
    if value == nil then return "" end
    local ok, result = pcall(function() return tostring(value) end)
    if ok then return result end
    return "<unprintable>"
end

local function field(value)
    local result = text(value)
    result = string.gsub(result, "\t", " ")
    result = string.gsub(result, "\r", " ")
    result = string.gsub(result, "\n", " ")
    return result
end

local function split(value, separator)
    local result = {}
    local start = 1
    while true do
        local first, last = string.find(value, separator, start, true)
        if first == nil then
            table.insert(result, string.sub(value, start))
            break
        end
        table.insert(result, string.sub(value, start, first - 1))
        start = last + 1
    end
    return result
end

local function read_lines(path)
    local handle = assert(io.open(path, "rb"), "cannot read task file: " .. path)
    local result = {}
    for line in handle:lines() do
        if string.sub(line, 1, 1) == "\239" then
            -- Be tolerant of a UTF-8 BOM if an older Windows PowerShell wrote
            -- the task file with its default UTF-8 encoding.
            line = string.sub(line, 4)
        end
        if line ~= "" and string.sub(line, 1, 1) ~= "#" then
            -- io:lines() strips LF but may preserve CR on Windows; remove it
            -- so the final boundary name is not looked up with a hidden suffix.
            line = string.gsub(line, "\r$", "")
            table.insert(result, line)
        end
    end
    handle:close()
    return result
end

local function safe_attr(object, key)
    local ok, value = pcall(function() return object:GetAttrs()[key] end)
    if ok then return value end
    return nil
end

local function tool_name(tool)
    return safe_attr(tool, "TOOLS_Name") or ""
end

local function tool_regid(tool)
    return safe_attr(tool, "TOOLS_RegID") or ""
end

local function list_values(object)
    local ok, values = pcall(function() return object:GetToolList(false) end)
    if ok and values ~= nil then return values end
    return {}
end

local function find_in_list(values, name)
    for _, tool in pairs(values) do
        if tool_name(tool) == name then return tool end
    end
    return nil
end

local function find_tool(comp, name)
    local ok, direct = pcall(function() return comp:FindTool(name) end)
    if ok and direct ~= nil then return direct end
    local direct_list = find_in_list(list_values(comp), name)
    if direct_list ~= nil then return direct_list end
    -- GroupOperator children are not guaranteed to be returned by the parent
    -- composition's FindTool.  Search each group through both APIs when the
    -- host exposes them.
    for _, group in pairs(list_values(comp)) do
        if tool_regid(group) == "GroupOperator" then
            local nested_ok, nested = pcall(function() return group:FindTool(name) end)
            if nested_ok and nested ~= nil then return nested end
            local nested_list = find_in_list(list_values(group), name)
            if nested_list ~= nil then return nested_list end
        end
    end
    return nil
end

local function output_of(tool)
    local ok, output = pcall(function() return tool.Output end)
    if ok and output ~= nil then return output end
    ok, output = pcall(function() return tool.MainOutput1 end)
    if ok and output ~= nil then return output end
    return nil
end

local function exists(path)
    if bmd ~= nil and bmd.fileexists ~= nil then
        local ok, result = pcall(function() return bmd.fileexists(path) end)
        if ok and result then return true end
    end
    local handle = io.open(path, "rb")
    if handle == nil then return false end
    handle:close()
    return true
end

local function remove(path)
    if path ~= nil and path ~= "" then pcall(function() os.remove(path) end) end
end

local function sequence_path(path)
    if string.sub(path, -4) == ".png" then
        return string.sub(path, 1, -5) .. "0000.png"
    end
    return path .. "0000.png"
end

local function wait_for_artifact(path, attempts)
    local sequence = sequence_path(path)
    for attempt = 1, attempts do
        if exists(path) then return path, attempt end
        if exists(sequence) then return sequence, attempt end
        os.execute("ping -n 2 127.0.0.1 > nul")
    end
    return nil, attempts
end

local function emit(handle, case_id, boundary, status, requested, artifact, render_ok, render_value, error)
    local values = {
        field(case_id), field(boundary), field(status), field(requested),
        field(artifact), field(render_ok), field(render_value), field(error)
    }
    handle:write(table.concat(values, "\t") .. "\n")
    handle:flush()
    print("RESULT=" .. table.concat(values, "|"))
end

local fusion = assert(bmd.scriptapp("Fusion", "localhost"), "Fusion scripting endpoint unavailable")
local comp = assert(fusion:GetCurrentComp(), "no current Fusion composition")
local records = assert(io.open(records_path, "wb"), "cannot write records file: " .. records_path)
records:write("# schema=psd2fusion-parity-004-fusion-boundary-record.v1\n")
print("HOST=Fusion_current_comp")
print("TASK_FILE=" .. field(task_path))
print("RECORD_FILE=" .. field(records_path))

local function run_case(parts)
    local case_id = parts[1]
    local scope = parts[2]
    local comp_path = parts[3]
    local output_dir = parts[4]
    local specifications = split(parts[5] or "", "|")
    local pasted = false
    local undo_started = false
    local lock_started = false
    local before_count = 0
    for _, _ in pairs(list_values(comp)) do before_count = before_count + 1 end

    local lock_ok = pcall(function() comp:Lock() end)
    lock_started = lock_ok
    local undo_ok = pcall(function() comp:StartUndo("PARITY-004 boundary probe " .. case_id) end)
    undo_started = undo_ok
    local paste_ok, paste_error = pcall(function()
        local settings = assert(bmd.readfile(comp_path), "composition read failed")
        local result = comp:Paste(settings)
        assert(result ~= false, "composition paste failed")
        pasted = true
        comp:SetAttrs({
            COMPN_GlobalStart = 0,
            COMPN_GlobalEnd = 0,
            COMPN_RenderStart = 0,
            COMPN_RenderEnd = 0
        })
    end)

    if not paste_ok then
        for _, specification in ipairs(specifications) do
            local pair = split(specification, "=")
            emit(records, case_id, pair[1] or "", "PASTE_FAILED", "", "", false, "", paste_error)
        end
    else
        for _, specification in ipairs(specifications) do
            local pair = split(specification, "=")
            local boundary = pair[1] or ""
            local name = pair[2] or ""
            local safe_label = string.gsub(boundary, "[^%w_%-]", "_")
            local requested = output_dir .. "\\" .. safe_label .. ".png"
            local tool = find_tool(comp, name)
            if tool == nil then
                emit(records, case_id, boundary, "TOOL_MISSING", requested, "", false, "", "tool_not_found:" .. name)
            else
                local source = output_of(tool)
                if source == nil then
                    emit(records, case_id, boundary, "OUTPUT_MISSING", requested, "", false, "", "tool_output_not_found:" .. name)
                else
                    remove(requested)
                    remove(sequence_path(requested))
                    local saver_ok, saver = pcall(function() return comp:AddTool("Saver", -2, 0) end)
                    if not saver_ok or saver == nil then
                        emit(records, case_id, boundary, "SAVER_FAILED", requested, "", false, "", text(saver))
                    else
                        local configure_ok, configure_error = pcall(function()
                            saver:SetAttrs({TOOLS_Name = "P4FB_Saver_" .. safe_label})
                            saver:SetInput("Clip", requested)
                            saver:SetInput("PNGFormat.PreDivide", 1)
                            saver:SetInput("Input", source)
                        end)
                        if not configure_ok then
                            emit(records, case_id, boundary, "SAVER_CONFIG_FAILED", requested, "", false, "", configure_error)
                        else
                            local render_ok, render_value = pcall(function()
                                return comp:Render({FrameRange = "0", Wait = true, Tool = saver})
                            end)
                            local artifact, attempts = wait_for_artifact(requested, 12)
                            if artifact ~= nil then
                                emit(records, case_id, boundary, "ARTIFACT_READY", requested, artifact, render_ok, render_value, "")
                            elseif not render_ok then
                                emit(records, case_id, boundary, "RENDER_FAILED", requested, "", render_ok, render_value, "artifact_missing_after_render")
                            else
                                emit(records, case_id, boundary, "ARTIFACT_MISSING", requested, "", render_ok, render_value, "artifact_missing_after_" .. text(attempts) .. "_polls")
                            end
                        end
                    end
                end
            end
        end
    end

    if undo_started then
        pcall(function() comp:EndUndo(true) end)
        pcall(function() comp:Undo() end)
    end
    if lock_started then pcall(function() comp:Unlock() end) end
    local after_count = 0
    for _, _ in pairs(list_values(comp)) do after_count = after_count + 1 end
    print("CASE=" .. field(case_id) .. " SCOPE=" .. field(scope) .. " PASTE=" .. text(pasted) .. " RESTORED=" .. text(after_count == before_count))
end

for _, line in ipairs(read_lines(task_path)) do
    local parts = split(line, "\t")
    if #parts >= 5 then
        run_case(parts)
    else
        print("TASK_INVALID=" .. field(line))
    end
end

records:close()
print("DONE=true")
