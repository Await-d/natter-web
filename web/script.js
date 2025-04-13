// DOM 元素引用
let servicesList = document.getElementById('services-list');
let templatesList = document.getElementById('templates-list');
let servicesPanel = document.getElementById('services-panel');
let newServicePanel = document.getElementById('new-service-panel');
let serviceDetailsPanel = document.getElementById('service-details-panel');
let helpPanel = document.getElementById('help-panel');
let templatesPanel = document.getElementById('templates-panel');
let saveTemplateDialog = document.getElementById('save-template-dialog');

// 表单元素
let newServiceForm = document.getElementById('new-service-form');
let serviceMode = document.getElementById('service-mode');
let basicModeOptions = document.getElementById('basic-mode-options');
let advancedModeOptions = document.getElementById('advanced-mode-options');
let commandArgs = document.getElementById('command-args');
let targetPort = document.getElementById('target-port');
let udpMode = document.getElementById('udp-mode');
let forwardMethod = document.getElementById('forward-method');
let bindInterface = document.getElementById('bind-interface');
let bindPort = document.getElementById('bind-port');
let useUpnp = document.getElementById('use-upnp');
let stunServer = document.getElementById('stun-server');
let keepaliveServer = document.getElementById('keepalive-server');
let keepaliveInterval = document.getElementById('keepalive-interval');
let notificationScript = document.getElementById('notification-script');
let retryMode = document.getElementById('retry-mode');
let quitOnChange = document.getElementById('quit-on-change');
let autoRestart = document.getElementById('auto-restart');

// 详情页元素
let serviceId = document.getElementById('service-id');
let serviceStatus = document.getElementById('service-status');
let serviceRuntime = document.getElementById('service-runtime');
let serviceMappedAddress = document.getElementById('service-mapped-address');
let serviceCmdArgs = document.getElementById('service-cmd-args');
let serviceOutput = document.getElementById('service-output');
let lanStatus = document.getElementById('lan-status');
let wanStatus = document.getElementById('wan-status');
let natType = document.getElementById('nat-type');
let copyAddressBtn = document.getElementById('copy-address-btn');
let clearLogBtn = document.getElementById('clear-log-btn');
let autoScroll = document.getElementById('auto-scroll');

// 按钮
let refreshServiceBtn = document.getElementById('refresh-service-btn');
let restartServiceBtn = document.getElementById('restart-service-btn');
let stopServiceBtn = document.getElementById('stop-service-btn');
let deleteServiceBtn = document.getElementById('delete-service-btn');
let saveAsTemplateBtn = document.getElementById('save-as-template-btn');
let backToListBtn = document.getElementById('back-to-list-btn');
let refreshAllBtn = document.getElementById('refresh-all-btn');
let stopAllBtn = document.getElementById('stop-all-btn');
let helpBtn = document.getElementById('help-btn');
let closeHelpBtn = document.getElementById('close-help-btn');
let backFromTemplatesBtn = document.getElementById('back-from-templates-btn');
let saveConfigBtn = document.getElementById('save-config-btn');
let loadConfigBtn = document.getElementById('load-config-btn');

// 模板对话框元素
let templateName = document.getElementById('template-name');
let templateDescription = document.getElementById('template-description');
let confirmSaveTemplate = document.getElementById('confirm-save-template');
let cancelSaveTemplate = document.getElementById('cancel-save-template');

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
    deleteTemplate: '/api/templates/delete',
    installTool: '/api/tools/install',
    checkTool: '/api/tools/check'
};

// 工具状态信息
const toolsStatus = {
    'socat': {
        installed: false,
        checking: false
    },
    'gost': {
        installed: false,
        checking: false
    }
};

// 检查工具是否已安装
function checkToolInstalled(tool) {
    if (toolsStatus[tool].checking) return;

    toolsStatus[tool].checking = true;

    fetch(`${API.checkTool}?tool=${tool}`)
        .then(response => response.json())
        .then(data => {
            toolsStatus[tool].installed = data.installed;
            toolsStatus[tool].checking = false;

            // 更新安装按钮状态
            updateToolInstallButtons();

            // 如果在转发方法中选择了该工具但未安装，显示提示
            if (forwardMethod && forwardMethod.value === tool && !data.installed) {
                showToolInstallPrompt(tool);
            }
        })
        .catch(error => {
            console.error(`检查工具 ${tool} 安装状态出错:`, error);
            toolsStatus[tool].checking = false;
        });
}

// 更新工具安装按钮状态
function updateToolInstallButtons() {
    const socatBtn = document.getElementById('install-socat-btn');
    const gostBtn = document.getElementById('install-gost-btn');

    if (socatBtn) {
        if (toolsStatus['socat'].installed) {
            socatBtn.textContent = '已安装socat';
            socatBtn.classList.add('btn-success');
            socatBtn.classList.remove('btn-secondary');
            socatBtn.disabled = true;
        } else {
            socatBtn.textContent = '安装socat';
            socatBtn.classList.remove('btn-success');
            socatBtn.classList.add('btn-secondary');
            socatBtn.disabled = false;
        }
    }

    if (gostBtn) {
        if (toolsStatus['gost'].installed) {
            gostBtn.textContent = '已安装gost';
            gostBtn.classList.add('btn-success');
            gostBtn.classList.remove('btn-secondary');
            gostBtn.disabled = true;
        } else {
            gostBtn.textContent = '安装gost';
            gostBtn.classList.remove('btn-success');
            gostBtn.classList.add('btn-secondary');
            gostBtn.disabled = false;
        }
    }
}

// 显示工具安装提示
function showToolInstallPrompt(tool) {
    const toolName = tool.charAt(0).toUpperCase() + tool.slice(1);

    const notification = document.createElement('div');
    notification.className = 'notification warning tool-install-prompt';
    notification.innerHTML = `
        <div style="margin-bottom:10px;">检测到您选择了 <strong>${toolName}</strong> 作为转发方法，但系统中未安装该工具。</div>
        <button class="btn-primary install-now-btn" data-tool="${tool}">现在安装 ${toolName}</button>
    `;

    // 添加到页面
    document.body.appendChild(notification);

    // 显示通知
    setTimeout(() => {
        notification.classList.add('show');
    }, 10);

    // 添加安装按钮事件
    const installBtn = notification.querySelector('.install-now-btn');
    if (installBtn) {
        installBtn.addEventListener('click', function () {
            const toolToInstall = this.getAttribute('data-tool');
            installTool(toolToInstall);
            notification.classList.remove('show');
            setTimeout(() => {
                document.body.removeChild(notification);
            }, 300);
        });
    }

    // 自动关闭
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => {
            if (document.body.contains(notification)) {
                document.body.removeChild(notification);
            }
        }, 300);
    }, 15000);
}

// 事件监听器设置
document.addEventListener('DOMContentLoaded', function () {
    // 获取DOM元素
    servicesList = document.getElementById('services-list');
    templatesList = document.getElementById('templates-list');
    servicesPanel = document.getElementById('services-panel');
    newServicePanel = document.getElementById('new-service-panel');
    serviceDetailsPanel = document.getElementById('service-details-panel');
    helpPanel = document.getElementById('help-panel');
    templatesPanel = document.getElementById('templates-panel');
    serviceOutput = document.getElementById('service-output');

    // 服务详情页面元素
    serviceId = document.getElementById('service-id');
    serviceStatus = document.getElementById('service-status');
    serviceMappedAddress = document.getElementById('service-mapped-address');
    serviceRuntime = document.getElementById('service-runtime');
    serviceCmdArgs = document.getElementById('service-cmd-args');
    lanStatus = document.getElementById('lan-status');
    wanStatus = document.getElementById('wan-status');

    // 获取表单元素
    newServiceForm = document.getElementById('new-service-form');
    serviceMode = document.getElementById('service-mode');
    basicModeOptions = document.getElementById('basic-mode-options');
    advancedModeOptions = document.getElementById('advanced-mode-options');
    targetPort = document.getElementById('target-port');
    udpMode = document.getElementById('udp-mode');
    forwardMethod = document.getElementById('forward-method');
    bindInterface = document.getElementById('bind-interface');
    bindPort = document.getElementById('bind-port');
    useUpnp = document.getElementById('use-upnp');
    stunServer = document.getElementById('stun-server');
    keepaliveServer = document.getElementById('keepalive-server');
    keepaliveInterval = document.getElementById('keepalive-interval');
    notificationScript = document.getElementById('notification-script');
    retryMode = document.getElementById('retry-mode');
    quitOnChange = document.getElementById('quit-on-change');
    autoRestart = document.getElementById('auto-restart');
    commandArgs = document.getElementById('command-args');

    // 按钮元素
    saveConfigBtn = document.getElementById('save-config-btn');
    loadConfigBtn = document.getElementById('load-config-btn');
    helpBtn = document.getElementById('help-btn');
    closeHelpBtn = document.getElementById('close-help-btn');
    refreshAllBtn = document.getElementById('refresh-all-btn');
    stopAllBtn = document.getElementById('stop-all-btn');
    refreshServiceBtn = document.getElementById('refresh-service-btn');
    restartServiceBtn = document.getElementById('restart-service-btn');
    stopServiceBtn = document.getElementById('stop-service-btn');
    saveAsTemplateBtn = document.getElementById('save-as-template-btn');
    backToListBtn = document.getElementById('back-to-list-btn');
    copyAddressBtn = document.getElementById('copy-address-btn');
    clearLogBtn = document.getElementById('clear-log-btn');
    backFromTemplatesBtn = document.getElementById('back-from-templates-btn');
    confirmSaveTemplate = document.getElementById('confirm-save-template');
    cancelSaveTemplate = document.getElementById('cancel-save-template');
    deleteServiceBtn = document.getElementById('delete-service-btn');

    // 加载服务列表
    loadServices();

    // 设置页面刷新定时器 (每10秒刷新一次列表)
    setInterval(loadServices, 10000);

    // 检查工具安装状态
    checkToolInstalled('socat');
    checkToolInstalled('gost');

    // 安装工具按钮事件
    const installSocatBtn = document.getElementById('install-socat-btn');
    if (installSocatBtn) {
        installSocatBtn.addEventListener('click', function () {
            installTool('socat');
        });
    }

    const installGostBtn = document.getElementById('install-gost-btn');
    if (installGostBtn) {
        installGostBtn.addEventListener('click', function () {
            installTool('gost');
        });
    }

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

    // 转发方法说明
    const methodDescriptions = {
        'socket': {
            name: 'socket (内置)',
            desc: '纯Python实现，无需额外依赖',
            bestFor: '通用场景，最简单的设置'
        },
        'iptables': {
            name: 'iptables',
            desc: '使用Linux的iptables进行转发，需要root权限',
            bestFor: 'Linux系统，需要高性能转发'
        },
        'nftables': {
            name: 'nftables',
            desc: '使用Linux的nftables进行转发，需要root权限',
            bestFor: '新版Linux系统，功能更强大'
        },
        'socat': {
            name: 'socat',
            desc: '使用socat工具转发，需要安装socat',
            bestFor: '需要高级转发功能但无root权限'
        },
        'gost': {
            name: 'gost',
            desc: '使用gost工具转发，需要安装gost',
            bestFor: '需要加密转发、代理等高级功能'
        }
    };

    // 转发方法选择改变事件
    if (forwardMethod) {
        forwardMethod.addEventListener('change', function () {
            const method = this.value;
            if (methodDescriptions[method]) {
                const info = methodDescriptions[method];
                showNotification(`${info.name}: ${info.desc}<br>适用于: ${info.bestFor}`, 'info');

                // 检查是否需要安装工具
                if (method === 'socat' || method === 'gost') {
                    checkToolInstalled(method);
                }
            }
        });
    }

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

        // 格式化地址显示
        const addressDisplay = service.mapped_address || '等待映射...';

        // 填充服务信息
        const mappedAddress = card.querySelector('.service-mapped-address');
        // 在标题处显示简短地址（只保留主机名/IP和端口）
        mappedAddress.textContent = formatAddressShort(addressDisplay);

        // 在卡片体中显示完整地址
        const mappedAddressFull = card.querySelector('.service-mapped-address-full');
        mappedAddressFull.textContent = addressDisplay;

        // 添加复制按钮事件
        const copyBtn = card.querySelector('.copy-address-btn');
        if (copyBtn) {
            copyBtn.addEventListener('click', function (e) {
                e.stopPropagation(); // 阻止事件冒泡
                copyToClipboard(addressDisplay);
                showNotification('地址已复制到剪贴板', 'success');
            });
        }

        // 设置服务状态和颜色
        const status = card.querySelector('.service-status');
        status.textContent = service.status;

        // 根据状态添加不同的样式类
        if (service.status === 'OPEN' || service.running) {
            status.classList.add('service-status-running');
            status.textContent = '运行中';
        } else if (service.status === 'CLOSED' || !service.running) {
            status.classList.add('service-status-stopped');
            status.textContent = '已停止';
        } else {
            status.classList.add('service-status-waiting');
            status.textContent = '等待中';
        }

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

// 显示服务详情
function showServiceDetails(id) {
    currentServiceId = id;

    // 隐藏其他面板
    servicesPanel.style.display = 'none';
    newServicePanel.style.display = 'none';
    helpPanel.style.display = 'none';
    templatesPanel.style.display = 'none';

    // 显示服务详情面板
    serviceDetailsPanel.style.display = 'block';

    // 设置服务ID显示
    serviceId.textContent = id;

    // 初始加载
    loadServiceDetails(id);

    // 设置定时刷新
    if (refreshIntervalId) {
        clearInterval(refreshIntervalId);
    }
    refreshIntervalId = setInterval(() => loadServiceDetails(id), 3000);

    // 设置运行时间更新
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
            const addressDisplay = service.mapped_address || '未知';
            serviceMappedAddress.textContent = addressDisplay;

            // 设置复制按钮状态
            if (copyAddressBtn) {
                if (addressDisplay === '未知' || !service.running) {
                    copyAddressBtn.disabled = true;
                    copyAddressBtn.classList.add('btn-disabled');
                } else {
                    copyAddressBtn.disabled = false;
                    copyAddressBtn.classList.remove('btn-disabled');
                }
            }

            // 更新命令参数
            serviceCmdArgs.textContent = `python natter.py ${service.cmd_args.join(' ')}`;

            // 更新输出日志，限制最多显示100条
            let outputLines = service.last_output;
            if (outputLines.length > 100) {
                // 只保留最新的100条日志
                outputLines = outputLines.slice(-100);
                serviceOutput.textContent = `[显示最新100条日志，共${service.last_output.length}条]\n` + outputLines.join('\n');
            } else {
                serviceOutput.textContent = outputLines.join('\n');
            }

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
    if (!text || text === '等待映射...' || text === '未知') {
        showNotification('暂无可复制的地址', 'warning');
        return;
    }

    // 获取事件源（按钮）
    const button = event ? event.currentTarget : null;

    // 尝试使用现代Clipboard API
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text)
            .then(() => {
                showNotification('已复制到剪贴板: ' + text, 'success');
                showCopyFeedback(button);
            })
            .catch(err => {
                console.error('复制失败:', err);
                fallbackCopyToClipboard(text, button);
            });
    } else {
        // 回退到传统方法
        fallbackCopyToClipboard(text, button);
    }
}

// 传统复制方法（回退方案）
function fallbackCopyToClipboard(text, button) {
    try {
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
        showNotification('已复制到剪贴板: ' + text, 'success');
        showCopyFeedback(button);
    } catch (err) {
        console.error('复制失败:', err);
        showNotification('复制失败，请手动复制', 'error');
    }
}

// 显示复制成功的视觉反馈
function showCopyFeedback(button) {
    if (!button) return;

    // 保存原始文本
    const originalText = button.textContent;
    // 修改按钮文本和样式
    button.textContent = '已复制！';
    button.classList.add('copy-success');

    // 恢复原始状态
    setTimeout(() => {
        button.textContent = originalText;
        button.classList.remove('copy-success');
    }, 1500);
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
 * @param {string} message - 通知消息，可包含HTML
 * @param {string} type - 通知类型 ('success', 'error', 'warning', 'info')
 */
function showNotification(message, type = 'info') {
    // 创建通知元素
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.innerHTML = message; // 使用innerHTML支持HTML内容

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
    }, 5000); // 增加显示时间到5秒，因为可能有更多内容需要阅读
}

/**
 * 安装指定工具
 * @param {string} tool - 工具名称
 */
function installTool(tool) {
    showNotification(`正在安装 ${tool}，请稍候...`, 'info');

    fetch(API.installTool, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                tool: tool
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification(data.message, 'success');
                // 更新工具状态
                toolsStatus[tool].installed = true;
                updateToolInstallButtons();
            } else {
                showNotification(data.message, 'error');
            }
        })
        .catch(error => {
            console.error(`安装 ${tool} 出错:`, error);
            showNotification(`安装 ${tool} 时发生错误`, 'error');
        });
}

/**
 * 格式化地址为简短显示
 * @param {string} address - 完整地址
 * @returns {string} - 简短格式的地址
 */
function formatAddressShort(address) {
    if (!address || address === '等待映射...' || address === '未知') {
        return address;
    }

    try {
        // 从地址中提取主机名/IP和端口
        let result = address;

        // 移除协议部分 (tcp://, udp://)
        if (address.includes('://')) {
            result = address.split('://')[1];
        }

        // 如果地址过长，只保留主要部分
        if (result.length > 25) {
            const parts = result.split(':');
            if (parts.length > 1) {
                // 获取最后一部分作为端口
                const port = parts[parts.length - 1];
                // 获取IP或主机名的前15个字符
                const host = parts.slice(0, -1).join(':');
                const shortHost = host.length > 15 ? host.substring(0, 12) + '...' : host;
                return shortHost + ':' + port;
            }
        }

        return result;
    } catch (e) {
        console.error('格式化地址出错:', e);
        return address;
    }
}