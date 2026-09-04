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
local readback_path = arg and arg[3]
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

local function tool_names(object)
    local names = {}
    for _, tool in pairs(list_values(object)) do
        names[tool_name(tool)] = true
    end
    return names
end

local function delete_new_tools(object, before)
    local added = {}
    for _, tool in pairs(list_values(object)) do
        if not before[tool_name(tool)] then table.insert(added, tool) end
    end
    table.sort(added, function(left, right)
        -- Remove GroupOperator containers after their children.  Some Resolve
        -- builds expose nested tools through the composition tool list.
        local left_group = tool_regid(left) == "GroupOperator"
        local right_group = tool_regid(right) == "GroupOperator"
        if left_group ~= right_group then return not left_group end
        return tool_name(left) > tool_name(right)
    end)
    local failures = {}
    for _, tool in ipairs(added) do
        local name = tool_name(tool)
        local ok, error_value = pcall(function() tool:Delete() end)
        if not ok then table.insert(failures, name .. ":" .. text(error_value)) end
    end
    return #added, failures
end

local function find_in_list(values, name)
    for _, tool in pairs(values) do
        if tool_name(tool) == name then return tool end
    end
    return nil
end

local function find_tool(container, name)
    -- Search direct children first so the returned owner is the container in
    -- which a temporary Saver must be created.  A root FindTool call may find
    -- nested tools but does not expose their owning GroupOperator.
    local values = list_values(container)
    local direct = find_in_list(values, name)
    if direct ~= nil then return direct, container end
    for _, group in pairs(values) do
        if tool_regid(group) == "GroupOperator" then
            local nested, owner = find_tool(group, name)
            if nested ~= nil then return nested, owner end
        end
    end
    return nil, nil
end

local function output_of(tool)
    if tool_regid(tool) == "GroupOperator" then
        local group_ok, group_output = pcall(function() return tool.MainOutput1 end)
        if group_ok and group_output ~= nil then return group_output end
    end
    local ok, output = pcall(function() return tool.Output end)
    if ok and output ~= nil then return output end
    ok, output = pcall(function() return tool.MainOutput1 end)
    if ok and output ~= nil then return output end
    return nil
end

local function safe_input(tool, name)
    local ok, value = pcall(function() return tool:GetInput(name) end)
    if ok then return value end
    return nil
end

local function connected_source(tool, name)
    local input_ok, input = pcall(function() return tool[name] end)
    if not input_ok or input == nil then return "" end
    local output_ok, output = pcall(function() return input:GetConnectedOutput() end)
    if not output_ok or output == nil then return "" end
    local source_ok, source = pcall(function() return output:GetTool() end)
    if not source_ok or source == nil then return "" end
    return tool_name(source)
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

local function emit_readback(handle, case_id, boundary, tool)
    if handle == nil then return end
    local values = {
        field(case_id), field(boundary), field(tool_name(tool)), field(tool_regid(tool)),
        field(output_of(tool) ~= nil),
        field(safe_input(tool, "ApplyMode")), field(safe_input(tool, "Blend")),
        field(safe_input(tool, "Operator")), field(safe_input(tool, "ProcessAlpha")),
        field(safe_input(tool, "Clip1.PNGFormat.PostMultiply")),
        field(connected_source(tool, "Input")), field(connected_source(tool, "Background")),
        field(connected_source(tool, "Foreground")), field(connected_source(tool, "MainInput1")),
        field(safe_input(tool, "Comments")),
    }
    handle:write(table.concat(values, "\t") .. "\n")
    handle:flush()
end

local fusion = assert(bmd.scriptapp("Fusion", "localhost"), "Fusion scripting endpoint unavailable")
local comp = assert(fusion:GetCurrentComp(), "no current Fusion composition")
local records = assert(io.open(records_path, "wb"), "cannot write records file: " .. records_path)
records:write("# schema=psd2fusion-parity-004-fusion-boundary-record.v1\n")
local readback = nil
if readback_path ~= nil and readback_path ~= "" then
    readback = assert(io.open(readback_path, "wb"), "cannot write readback file: " .. readback_path)
    readback:write("# schema=psd2fusion-parity-004-fusion-runtime-readback.v1\n")
    readback:write("# case_id\tboundary\ttool\tregid\toutput_available\tapply_mode\tblend\toperator\tprocess_alpha\tpost_multiply\tinput_source\tbackground_source\tforeground_source\tmain_input_source\tcomments\n")
end
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
    local before_names = tool_names(comp)
    local before_attrs = comp:GetAttrs() or {}
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
            local tool, owner = find_tool(comp, name)
            if tool == nil then
                emit(records, case_id, boundary, "TOOL_MISSING", requested, "", false, "", "tool_not_found:" .. name)
            else
                emit_readback(readback, case_id, boundary, tool)
                local source = output_of(tool)
                if source == nil then
                    emit(records, case_id, boundary, "OUTPUT_MISSING", requested, "", false, "", "tool_output_not_found:" .. name)
                else
                    remove(requested)
                    remove(sequence_path(requested))
                    local saver_ok, saver = pcall(function() return owner:AddTool("Saver", -2, 0) end)
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

    if lock_started then pcall(function() comp:Unlock() end) end
    local deleted_count, delete_failures = delete_new_tools(comp, before_names)
    pcall(function()
        comp:SetAttrs({
            COMPN_GlobalStart = before_attrs.COMPN_GlobalStart,
            COMPN_GlobalEnd = before_attrs.COMPN_GlobalEnd,
            COMPN_RenderStart = before_attrs.COMPN_RenderStart,
            COMPN_RenderEnd = before_attrs.COMPN_RenderEnd
        })
    end)
    if undo_started then pcall(function() comp:EndUndo(true) end) end
    local after_count = 0
    for _, _ in pairs(list_values(comp)) do after_count = after_count + 1 end
    print("CASE=" .. field(case_id) .. " SCOPE=" .. field(scope)
        .. " PASTE=" .. text(pasted) .. " RESTORED=" .. text(after_count == before_count)
        .. " DELETED=" .. text(deleted_count) .. " DELETE_FAILURES=" .. text(#delete_failures))
    for _, failure in ipairs(delete_failures) do print("DELETE_FAILURE=" .. field(failure)) end
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
if readback ~= nil then readback:close() end
print("DONE=true")
