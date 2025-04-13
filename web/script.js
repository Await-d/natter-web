// DOM 元素引用
const servicesList = document.getElementById('services-list');
const serviceDetailsPanel = document.getElementById('service-details-panel');
const servicesPanel = document.getElementById('services-panel');
const newServicePanel = document.getElementById('new-service-panel');
const helpPanel = document.getElementById('help-panel');
const templatesPanel = document.getElementById('templates-panel');
const saveTemplateDialog = document.getElementById('save-template-dialog');
const templatesList = document.getElementById('templates-list');

// 表单元素
const newServiceForm = document.getElementById('new-service-form');
const serviceMode = document.getElementById('service-mode');
const basicModeOptions = document.getElementById('basic-mode-options');
const advancedModeOptions = document.getElementById('advanced-mode-options');
const commandArgs = document.getElementById('command-args');
const targetPort = document.getElementById('target-port');
const udpMode = document.getElementById('udp-mode');
const forwardMethod = document.getElementById('forward-method');
const bindInterface = document.getElementById('bind-interface');
const bindPort = document.getElementById('bind-port');
const useUpnp = document.getElementById('use-upnp');
const stunServer = document.getElementById('stun-server');
const keepaliveServer = document.getElementById('keepalive-server');
const keepaliveInterval = document.getElementById('keepalive-interval');
const notificationScript = document.getElementById('notification-script');
const retryMode = document.getElementById('retry-mode');
const quitOnChange = document.getElementById('quit-on-change');
const autoRestart = document.getElementById('auto-restart');

// 详情页元素
const serviceId = document.getElementById('service-id');
const serviceStatus = document.getElementById('service-status');
const serviceRuntime = document.getElementById('service-runtime');
const serviceMappedAddress = document.getElementById('service-mapped-address');
const serviceCmdArgs = document.getElementById('service-cmd-args');
const serviceOutput = document.getElementById('service-output');
const lanStatus = document.getElementById('lan-status');
const wanStatus = document.getElementById('wan-status');
const natType = document.getElementById('nat-type');
const copyAddressBtn = document.getElementById('copy-address-btn');
const clearLogBtn = document.getElementById('clear-log-btn');
const autoScroll = document.getElementById('auto-scroll');

// 按钮
const refreshServiceBtn = document.getElementById('refresh-service-btn');
const restartServiceBtn = document.getElementById('restart-service-btn');
const stopServiceBtn = document.getElementById('stop-service-btn');
const deleteServiceBtn = document.getElementById('delete-service-btn');
const saveAsTemplateBtn = document.getElementById('save-as-template-btn');
const backToListBtn = document.getElementById('back-to-list-btn');
const refreshAllBtn = document.getElementById('refresh-all-btn');
const stopAllBtn = document.getElementById('stop-all-btn');
const helpBtn = document.getElementById('help-btn');
const closeHelpBtn = document.getElementById('close-help-btn');
const backFromTemplatesBtn = document.getElementById('back-from-templates-btn');
const saveConfigBtn = document.getElementById('save-config-btn');
const loadConfigBtn = document.getElementById('load-config-btn');

// 模板对话框元素
const templateName = document.getElementById('template-name');
const templateDescription = document.getElementById('template-description');
const confirmSaveTemplate = document.getElementById('confirm-save-template');
const cancelSaveTemplate = document.getElementById('cancel-save-template');

// 当前视图状态
let currentServiceId = null;
let refreshIntervalId = null;
let runtimeIntervalId = null;
const servicesRuntime = {};
let previousView = null;

// API 端点
const API = {
    listServices: '/api/services',
    getService: '/api/service',
    startService: '/api/services/start',
    stopService: '/api/services/stop',
    deleteService: '/api/services/delete',
    restartService: '/api/services/restart',
    stopAllServices: '/api/services/stop-all',
    setAutoRestart: '/api/services/auto-restart',
    clearLogs: '/api/services/clear-logs',
    listTemplates: '/api/templates',
    saveTemplate: '/api/templates/save',
    deleteTemplate: '/api/templates/delete'
};

// 事件监听器设置
document.addEventListener('DOMContentLoaded', function () {
    // 加载服务列表
    loadServices();

    // 设置页面刷新定时器 (每10秒刷新一次列表)
    setInterval(loadServices, 10000);

    // 模式切换事件
    serviceMode.addEventListener('change', function () {
        if (this.value === 'basic') {
            basicModeOptions.style.display = 'block';
            advancedModeOptions.style.display = 'none';
        } else {
            basicModeOptions.style.display = 'none';
            advancedModeOptions.style.display = 'block';
        }
    });

    // 选项卡切换
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', function () {
            // 移除所有激活状态
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(content => content.style.display = 'none');

            // 激活当前选项卡
            this.classList.add('active');
            const tabId = this.getAttribute('data-tab');
            document.getElementById(tabId + '-tab').style.display = 'block';
        });
    });

    // 表单提交事件
    newServiceForm.addEventListener('submit', function (e) {
        e.preventDefault();
        startNewService();
    });

    // 配置保存和加载按钮
    if (saveConfigBtn) {
        saveConfigBtn.addEventListener('click', function () {
            showSaveTemplateDialog();
        });
    }

    if (loadConfigBtn) {
        loadConfigBtn.addEventListener('click', function () {
            showTemplatesPanel();
        });
    }

    // 帮助按钮
    if (helpBtn) {
        helpBtn.addEventListener('click', function () {
            showHelpPanel();
        });
    }

    if (closeHelpBtn) {
        closeHelpBtn.addEventListener('click', function () {
            hideHelpPanel();
        });
    }

    // 批量操作按钮
    if (refreshAllBtn) {
        refreshAllBtn.addEventListener('click', function () {
            loadServices();
        });
    }

    if (stopAllBtn) {
        stopAllBtn.addEventListener('click', function () {
            stopAllServices();
        });
    }

    // 服务详情页按钮事件
    if (refreshServiceBtn) {
        refreshServiceBtn.addEventListener('click', function () {
            loadServiceDetails(currentServiceId);
        });
    }

    if (restartServiceBtn) {
        restartServiceBtn.addEventListener('click', function () {
            restartService(currentServiceId);
        });
    }

    if (stopServiceBtn) {
        stopServiceBtn.addEventListener('click', function () {
            stopService(currentServiceId);
        });
    }

    if (saveAsTemplateBtn) {
        saveAsTemplateBtn.addEventListener('click', function () {
            showSaveTemplateDialog(currentServiceId);
        });
    }

    if (backToListBtn) {
        backToListBtn.addEventListener('click', function () {
            showServicesList();
        });
    }

    if (copyAddressBtn) {
        copyAddressBtn.addEventListener('click', function () {
            copyToClipboard(serviceMappedAddress.textContent);
        });
    }

    if (clearLogBtn) {
        clearLogBtn.addEventListener('click', function () {
            clearServiceLogs(currentServiceId);
        });
    }

    // 模板面板返回按钮
    if (backFromTemplatesBtn) {
        backFromTemplatesBtn.addEventListener('click', function () {
            hideTemplatesPanel();
        });
    }

    // 保存模板对话框按钮
    if (confirmSaveTemplate) {
        confirmSaveTemplate.addEventListener('click', function () {
            saveTemplateFromDialog();
        });
    }

    if (cancelSaveTemplate) {
        cancelSaveTemplate.addEventListener('click', function () {
            hideSaveTemplateDialog();
        });
    }

    // 添加删除服务按钮的事件监听
    if (deleteServiceBtn) {
        deleteServiceBtn.addEventListener('click', function () {
            if (confirm('确定要删除此服务吗？此操作不可恢复。')) {
                deleteService(currentServiceId);
            }
        });
    }
});

// 加载服务列表
function loadServices() {
    fetch(API.listServices)
        .then(response => response.json())
        .then(data => {
            renderServicesList(data.services);
        })
        .catch(error => {
            console.error('加载服务列表出错:', error);
            servicesList.innerHTML = '<div class="no-services">加载服务失败，请刷新页面重试。</div>';
        });
}

// 渲染服务列表
function renderServicesList(services) {
    // 清空列表
    servicesList.innerHTML = '';

    if (services.length === 0) {
        servicesList.innerHTML = '<div class="no-services">没有运行中的服务</div>';
        return;
    }

    // 为每个服务创建卡片
    services.forEach(service => {
        const template = document.getElementById('service-card-template');
        const clone = document.importNode(template.content, true);
        const card = clone.querySelector('.service-card');

        // 设置服务ID
        card.setAttribute('data-id', service.id);

        // 填充服务信息
        const mappedAddress = card.querySelector('.service-mapped-address');
        mappedAddress.textContent = service.mapped_address || '等待映射...';

        const status = card.querySelector('.service-status');
        status.textContent = service.status;
        setStatusColor(status, service.status);

        const cmdArgs = card.querySelector('.service-cmd-args');
        cmdArgs.textContent = '命令: ' + service.cmd_args.join(' ');

        const runtime = card.querySelector('.service-runtime');
        // 记录服务的启动时间
        servicesRuntime[service.id] = service.start_time;
        updateServiceRuntime(service, runtime);

        // 添加查看详情按钮事件
        const viewDetailsBtn = card.querySelector('.view-details-btn');
        viewDetailsBtn.addEventListener('click', function () {
            showServiceDetails(service.id);
        });

        // 添加停止服务按钮事件
        const stopBtn = card.querySelector('.stop-service-btn');
        stopBtn.addEventListener('click', function (e) {
            e.stopPropagation(); // 阻止事件冒泡
            stopService(service.id);
        });

        // 添加删除服务按钮
        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'btn-danger delete-service-btn';
        deleteBtn.textContent = '删除';
        deleteBtn.addEventListener('click', function (e) {
            e.stopPropagation(); // 阻止事件冒泡
            if (confirm('确定要删除此服务吗？此操作不可恢复。')) {
                deleteService(service.id);
            }
        });

        // 将删除按钮添加到卡片底部
        const cardFooter = card.querySelector('.service-card-footer');
        cardFooter.appendChild(deleteBtn);

        // 添加卡片到列表
        servicesList.appendChild(card);
    });
}

// 更新服务运行时间显示
function updateServiceRuntime(service, element) {
    if (!service.start_time) {
        element.textContent = '运行时间: N/A';
        return;
    }

    // 保存开始时间以便后续更新
    servicesRuntime[service.id] = service.start_time;

    const runtime = formatRuntime(Date.now() / 1000 - service.start_time);
    element.textContent = `运行时间: ${runtime}`;
}

// 格式化运行时间
function formatRuntime(seconds) {
    if (isNaN(seconds) || seconds < 0) {
        return 'N/A';
    }

    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);

    if (days > 0) {
        return `${days}天 ${hours}小时 ${minutes}分钟`;
    } else if (hours > 0) {
        return `${hours}小时 ${minutes}分钟 ${secs}秒`;
    } else if (minutes > 0) {
        return `${minutes}分钟 ${secs}秒`;
    } else {
        return `${secs}秒`;
    }
}

// 从基础模式构建参数
function buildArgsFromBasicMode() {
    let args = [];

    // 必须有目标端口
    if (!targetPort.value) {
        alert('请输入目标端口！');
        return null;
    }

    args.push('-p', targetPort.value);

    // 协议选择
    if (udpMode.checked) {
        args.push('-u');
    }

    // 转发方法
    if (forwardMethod.value !== 'socket') {
        args.push('-m', forwardMethod.value);
    }

    // 网络设置
    if (bindInterface.value.trim()) {
        args.push('-i', bindInterface.value.trim());
    }

    if (bindPort.value.trim()) {
        args.push('-b', bindPort.value.trim());
    }

    if (useUpnp.checked) {
        args.push('-U');
    }

    // 高级设置
    if (stunServer.value.trim()) {
        args.push('-s', stunServer.value.trim());
    }

    if (keepaliveServer.value.trim()) {
        args.push('-h', keepaliveServer.value.trim());
    }

    if (keepaliveInterval.value.trim()) {
        args.push('-k', keepaliveInterval.value.trim());
    }

    if (notificationScript.value.trim()) {
        args.push('-e', notificationScript.value.trim());
    }

    if (retryMode.checked) {
        args.push('-r');
    }

    if (quitOnChange.checked) {
        args.push('-q');
    }

    return args;
}

// 启动新服务
function startNewService() {
    let args = [];
    let auto_restart = autoRestart.checked;

    if (serviceMode.value === 'basic') {
        // 基础模式，构建参数列表
        args = buildArgsFromBasicMode();
        if (!args) return;
    } else {
        // 高级模式，直接使用用户输入的命令参数
        if (!commandArgs.value.trim()) {
            alert('请输入命令参数！');
            return;
        }

        args = commandArgs.value.trim().split(/\s+/);
    }

    // 发送请求启动服务
    fetch(API.startService, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                args: args,
                auto_restart: auto_restart
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.service_id) {
                alert('服务启动成功！');
                loadServices();

                // 重置表单
                newServiceForm.reset();
            } else {
                alert('服务启动失败：' + (data.error || '未知错误'));
            }
        })
        .catch(error => {
            console.error('启动服务出错:', error);
            alert('启动服务时发生错误，请检查控制台查看详情。');
        });
}

// 停止服务
function stopService(id) {
    if (!confirm('确定要停止此服务吗？')) {
        return;
    }

    fetch(API.stopService, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                id: id
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('服务已停止！');

                // 如果当前正在查看该服务的详情，则返回列表页
                if (currentServiceId === id) {
                    showServicesList();
                }

                // 刷新服务列表
                loadServices();
            } else {
                alert('停止服务失败：' + (data.error || '未知错误'));
            }
        })
        .catch(error => {
            console.error('停止服务出错:', error);
            alert('停止服务时发生错误，请检查控制台查看详情。');
        });
}

// 重启服务
function restartService(id) {
    if (!confirm('确定要重启此服务吗？')) {
        return;
    }

    fetch(API.restartService, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                id: id
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('服务已重启！');
                loadServiceDetails(id);
            } else {
                alert('重启服务失败：' + (data.error || '未知错误'));
            }
        })
        .catch(error => {
            console.error('重启服务出错:', error);
            alert('重启服务时发生错误，请检查控制台查看详情。');
        });
}

// 停止所有服务
function stopAllServices() {
    if (!confirm('确定要停止所有运行中的服务吗？')) {
        return;
    }

    fetch(API.stopAllServices, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({})
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert(`已停止 ${data.stopped_count} 个服务！`);

                // 如果当前在查看服务详情，则返回列表页
                if (currentServiceId) {
                    showServicesList();
                } else {
                    loadServices();
                }
            } else {
                alert('停止服务失败：' + (data.error || '未知错误'));
            }
        })
        .catch(error => {
            console.error('停止所有服务出错:', error);
            alert('停止服务时发生错误，请检查控制台查看详情。');
        });
}

// 设置自动重启
function setAutoRestart(id, enabled) {
    fetch(API.setAutoRestart, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                id: id,
                enabled: enabled
            })
        })
        .then(response => response.json())
        .then(data => {
            if (!data.success) {
                alert('设置自动重启失败：' + (data.error || '未知错误'));
            }
        })
        .catch(error => {
            console.error('设置自动重启出错:', error);
        });
}

// 清空服务日志
function clearServiceLogs(id) {
    fetch(API.clearLogs, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                id: id
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                serviceOutput.textContent = '';
            } else {
                alert('清空日志失败：' + (data.error || '未知错误'));
            }
        })
        .catch(error => {
            console.error('清空日志出错:', error);
            alert('清空日志时发生错误，请检查控制台查看详情。');
        });
}

// 显示服务详情页
function showServiceDetails(id) {
    currentServiceId = id;

    // 隐藏其他面板
    servicesPanel.style.display = 'none';
    newServicePanel.style.display = 'none';
    helpPanel.style.display = 'none';
    templatesPanel.style.display = 'none';

    // 显示详情面板
    serviceDetailsPanel.style.display = 'block';

    // 加载服务详情
    loadServiceDetails(id);

    // 设置自动刷新
    if (refreshIntervalId) {
        clearInterval(refreshIntervalId);
    }
    refreshIntervalId = setInterval(() => loadServiceDetails(id), 3000);

    // 更新运行时间
    if (runtimeIntervalId) {
        clearInterval(runtimeIntervalId);
    }
    runtimeIntervalId = setInterval(updateDetailRuntime, 1000);
}

// 更新详情页运行时间
function updateDetailRuntime() {
    if (!currentServiceId || !servicesRuntime[currentServiceId]) return;

    const startTime = servicesRuntime[currentServiceId];
    const runtime = formatRuntime(Date.now() / 1000 - startTime);
    serviceRuntime.textContent = runtime;
}

// 加载服务详情
function loadServiceDetails(id) {
    fetch(`${API.getService}?id=${id}`)
        .then(response => response.json())
        .then(data => {
            if (!data.service) {
                alert('无法找到该服务，可能已被删除。');
                showServicesList();
                return;
            }

            const service = data.service;

            // 更新服务ID
            serviceId.textContent = `#${service.id}`;

            // 更新状态
            serviceStatus.textContent = service.running ? '运行中' : '已停止';
            serviceStatus.className = 'value ' + (service.running ? 'text-success' : 'text-danger');

            // 更新映射地址
            serviceMappedAddress.textContent = service.mapped_address || '未知';

            // 更新命令参数
            serviceCmdArgs.textContent = `python natter.py ${service.cmd_args.join(' ')}`;

            // 更新输出日志
            serviceOutput.textContent = service.last_output.join('\n');
            if (autoScroll && autoScroll.checked) {
                serviceOutput.scrollTop = serviceOutput.scrollHeight;
            }

            // 更新状态面板
            lanStatus.textContent = service.lan_status || '未知';
            wanStatus.textContent = service.wan_status || '未知';
            natType.textContent = service.nat_type || '未知';

            // 根据状态设置颜色
            setStatusColor(lanStatus, service.lan_status);
            setStatusColor(wanStatus, service.wan_status);

            // 保存开始时间以便更新运行时间
            servicesRuntime[service.id] = service.start_time;
            updateDetailRuntime();
        })
        .catch(error => {
            console.error('加载服务详情出错:', error);
            serviceOutput.textContent = '加载服务详情失败，请刷新重试。';
        });
}

// 设置状态显示的颜色
function setStatusColor(element, status) {
    element.className = 'status-value';

    if (status === 'OPEN') {
        element.classList.add('text-success');
    } else if (status === 'CLOSED') {
        element.classList.add('text-danger');
    } else if (status === 'UNKNOWN') {
        element.classList.add('text-warning');
    }
}

// 返回服务列表页
function showServicesList() {
    // 清除自动刷新定时器
    if (refreshIntervalId) {
        clearInterval(refreshIntervalId);
        refreshIntervalId = null;
    }

    if (runtimeIntervalId) {
        clearInterval(runtimeIntervalId);
        runtimeIntervalId = null;
    }

    // 隐藏其他面板
    serviceDetailsPanel.style.display = 'none';
    helpPanel.style.display = 'none';
    templatesPanel.style.display = 'none';

    // 显示服务列表和新建服务面板
    servicesPanel.style.display = 'block';
    newServicePanel.style.display = 'block';

    // 重置当前服务ID
    currentServiceId = null;

    // 刷新服务列表
    loadServices();
}

// 显示帮助面板
function showHelpPanel() {
    previousView = {
        servicesPanel: servicesPanel.style.display,
        newServicePanel: newServicePanel.style.display,
        serviceDetailsPanel: serviceDetailsPanel.style.display,
        templatesPanel: templatesPanel.style.display
    };

    // 隐藏其他面板
    servicesPanel.style.display = 'none';
    newServicePanel.style.display = 'none';
    serviceDetailsPanel.style.display = 'none';
    templatesPanel.style.display = 'none';

    // 显示帮助面板
    helpPanel.style.display = 'block';
}

// 隐藏帮助面板
function hideHelpPanel() {
    helpPanel.style.display = 'none';

    if (previousView) {
        servicesPanel.style.display = previousView.servicesPanel;
        newServicePanel.style.display = previousView.newServicePanel;
        serviceDetailsPanel.style.display = previousView.serviceDetailsPanel;
        templatesPanel.style.display = previousView.templatesPanel;
    } else {
        showServicesList();
    }
}

// 显示模板面板
function showTemplatesPanel() {
    previousView = {
        servicesPanel: servicesPanel.style.display,
        newServicePanel: newServicePanel.style.display,
        serviceDetailsPanel: serviceDetailsPanel.style.display,
        helpPanel: helpPanel.style.display
    };

    // 隐藏其他面板
    servicesPanel.style.display = 'none';
    newServicePanel.style.display = 'none';
    serviceDetailsPanel.style.display = 'none';
    helpPanel.style.display = 'none';

    // 显示模板面板
    templatesPanel.style.display = 'block';

    // 加载模板列表
    loadTemplates();
}

// 隐藏模板面板
function hideTemplatesPanel() {
    templatesPanel.style.display = 'none';

    if (previousView) {
        servicesPanel.style.display = previousView.servicesPanel;
        newServicePanel.style.display = previousView.newServicePanel;
        serviceDetailsPanel.style.display = previousView.serviceDetailsPanel;
        helpPanel.style.display = previousView.helpPanel;
    } else {
        showServicesList();
    }
}

// 加载模板列表
function loadTemplates() {
    fetch(API.listTemplates)
        .then(response => response.json())
        .then(data => {
            renderTemplatesList(data.templates);
        })
        .catch(error => {
            console.error('加载模板列表出错:', error);
            templatesList.innerHTML = '<div class="no-services">加载模板失败，请刷新页面重试。</div>';
        });
}

// 渲染模板列表
function renderTemplatesList(templates) {
    if (!templates || templates.length === 0) {
        templatesList.innerHTML = '<div class="no-services">没有保存的模板。</div>';
        return;
    }

    templatesList.innerHTML = '';
    const template = document.getElementById('template-card-template');

    templates.forEach(tmpl => {
        const card = template.content.cloneNode(true);
        const templateCard = card.querySelector('.template-card');

        // 更新模板卡片数据
        templateCard.dataset.id = tmpl.id;
        card.querySelector('.template-name').textContent = tmpl.name;

        const date = new Date(tmpl.created_at * 1000);
        card.querySelector('.template-date').textContent = date.toLocaleString();

        card.querySelector('.template-description').textContent = `描述: ${tmpl.description || '无描述'}`;
        card.querySelector('.template-cmd-args').textContent = `命令: python natter.py ${tmpl.cmd_args.join(' ')}`;

        // 为卡片按钮添加事件
        card.querySelector('.use-template-btn').addEventListener('click', function () {
            useTemplate(tmpl);
        });

        card.querySelector('.delete-template-btn').addEventListener('click', function (e) {
            e.stopPropagation();
            deleteTemplate(tmpl.id);
        });

        templatesList.appendChild(card);
    });
}

// 使用模板
function useTemplate(tmpl) {
    // 切换到高级模式
    serviceMode.value = 'advanced';
    basicModeOptions.style.display = 'none';
    advancedModeOptions.style.display = 'block';

    // 填充命令参数
    commandArgs.value = tmpl.cmd_args.join(' ');

    // 隐藏模板面板
    hideTemplatesPanel();
}

// 删除模板
function deleteTemplate(id) {
    if (!confirm('确定要删除此模板吗？此操作不可撤销。')) {
        return;
    }

    fetch(API.deleteTemplate, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                id: id
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('模板已删除！');
                loadTemplates();
            } else {
                alert('删除模板失败：' + (data.error || '未知错误'));
            }
        })
        .catch(error => {
            console.error('删除模板出错:', error);
            alert('删除模板时发生错误，请检查控制台查看详情。');
        });
}

// 显示保存模板对话框
function showSaveTemplateDialog(serviceId) {
    // 清空输入框
    templateName.value = '';
    templateDescription.value = '';

    // 保存当前正在查看的服务ID（如果有）
    saveTemplateDialog.dataset.serviceId = serviceId || '';

    // 显示对话框
    saveTemplateDialog.classList.add('active');
}

// 隐藏保存模板对话框
function hideSaveTemplateDialog() {
    saveTemplateDialog.classList.remove('active');
}

// 从对话框保存模板
function saveTemplateFromDialog() {
    const name = templateName.value.trim();
    if (!name) {
        alert('请输入模板名称！');
        return;
    }

    let cmd_args = [];
    const serviceId = saveTemplateDialog.dataset.serviceId;

    if (serviceId) {
        // 从服务详情保存
        fetch(`${API.getService}?id=${serviceId}`)
            .then(response => response.json())
            .then(data => {
                if (!data.service) {
                    alert('无法找到该服务，可能已被删除。');
                    hideSaveTemplateDialog();
                    return;
                }

                saveTemplateToServer(name, templateDescription.value.trim(), data.service.cmd_args);
            })
            .catch(error => {
                console.error('获取服务详情出错:', error);
                alert('获取服务详情失败，无法保存模板。');
            });
    } else {
        // 从命令行参数保存
        if (serviceMode.value === 'basic') {
            cmd_args = buildArgsFromBasicMode();
            if (!cmd_args) return;
        } else {
            if (!commandArgs.value.trim()) {
                alert('请输入命令参数！');
                return;
            }
            cmd_args = commandArgs.value.trim().split(/\s+/);
        }

        saveTemplateToServer(name, templateDescription.value.trim(), cmd_args);
    }
}

// 保存模板到服务器
function saveTemplateToServer(name, description, cmd_args) {
    fetch(API.saveTemplate, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                name: name,
                description: description,
                cmd_args: cmd_args
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.template_id) {
                alert('模板保存成功！');
                hideSaveTemplateDialog();
            } else {
                alert('保存模板失败：' + (data.error || '未知错误'));
            }
        })
        .catch(error => {
            console.error('保存模板出错:', error);
            alert('保存模板时发生错误，请检查控制台查看详情。');
        });
}

// 复制文本到剪贴板
function copyToClipboard(text) {
    if (!text) return;

    // 创建临时输入框
    const tempInput = document.createElement('input');
    tempInput.value = text;
    document.body.appendChild(tempInput);

    // 选择并复制
    tempInput.select();
    document.execCommand('copy');

    // 移除临时输入框
    document.body.removeChild(tempInput);

    // 提示用户
    alert('已复制到剪贴板: ' + text);
}

/**
 * 删除指定的服务
 * @param {string} id - 服务ID
 */
function deleteService(id) {
    fetch(API.deleteService, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                id: id
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // 删除成功，返回服务列表
                showNotification('服务已成功删除', 'success');
                showServicesList();
                loadServices(); // 刷新服务列表
            } else {
                showNotification('删除服务失败', 'error');
            }
        })
        .catch(error => {
            console.error('删除服务出错:', error);
            showNotification('删除服务时发生错误', 'error');
        });
}

/**
 * 显示通知消息
 * @param {string} message - 通知消息
 * @param {string} type - 通知类型 ('success', 'error', 'warning', 'info')
 */
function showNotification(message, type = 'info') {
    // 创建通知元素
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;

    // 添加到页面
    document.body.appendChild(notification);

    // 显示通知
    setTimeout(() => {
        notification.classList.add('show');
    }, 10);

    // 自动删除通知
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => {
            document.body.removeChild(notification);
        }, 300);
    }, 3000);
}