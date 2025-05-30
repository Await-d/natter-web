// DOM 元素引用
let servicesList = document.getElementById('services-list');
let templatesList = document.getElementById('templates-list');
let servicesPanel = document.getElementById('services-panel');
let newServicePanel = document.getElementById('new-service-panel');
let serviceDetailsPanel = document.getElementById('service-details-panel');
let helpPanel = document.getElementById('help-panel');
let templatesPanel = document.getElementById('templates-panel');
let iyuuPanel = document.getElementById('iyuu-panel'); // IYUU推送设置面板
let saveTemplateDialog = document.getElementById('save-template-dialog');
let groupsPanel = document.getElementById('groups-panel'); // 分组管理面板
// 以下loginPanel相关代码已不再需要，因为登录功能已移至login.html
// let loginPanel = document.createElement('div');
// loginPanel.className = 'login-panel';
// loginPanel.style.display = 'none';

// 表单元素
let newServiceForm = document.getElementById('new-service-form');
let serviceMode = document.getElementById('service-mode');
let basicModeOptions = document.getElementById('basic-mode-options');
let advancedModeOptions = document.getElementById('advanced-mode-options');
let commandArgs = document.getElementById('command-args');
let targetPort = document.getElementById('target-port');
let targetIp = document.getElementById('target-ip'); // 新增: 获取目标IP输入框
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
let serviceGroup = document.getElementById('service-group'); // 新建服务分组选择

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

// IYUU推送相关DOM元素
let iyuuSettingsBtn = document.getElementById('iyuu-settings-btn'); // 设置按钮
let iyuuEnabled = document.getElementById('iyuu-enabled'); // 启用IYUU推送开关
let iyuuTokensList = document.getElementById('iyuu-tokens-list'); // 令牌列表容器
let newIyuuToken = document.getElementById('new-iyuu-token'); // 新令牌输入框
let addIyuuToken = document.getElementById('add-iyuu-token'); // 添加令牌按钮
let iyuuScheduleEnabled = document.getElementById('iyuu-schedule-enabled'); // 定时推送开关
let iyuuScheduleTime = document.getElementById('new-schedule-time'); // 调整为新的时间输入框ID
let iyuuScheduleMessage = document.getElementById('iyuu-schedule-message'); // 定时推送消息
let testIyuuPush = document.getElementById('test-iyuu-push'); // 测试推送按钮
let saveIyuuSettings = document.getElementById('save-iyuu-settings'); // 保存设置按钮
let backFromIyuuBtn = document.getElementById('back-from-iyuu-btn'); // 返回按钮

// 分组管理相关DOM元素
let groupsManagementBtn = document.getElementById('groups-management-btn');
let groupsList = document.getElementById('groups-list');
let newGroupName = document.getElementById('new-group-name');
let addGroupBtn = document.getElementById('add-group-btn');
let batchSourceGroup = document.getElementById('batch-source-group');
let batchTargetGroup = document.getElementById('batch-target-group');
let batchMoveBtn = document.getElementById('batch-move-btn');
let backFromGroupsBtn = document.getElementById('back-from-groups-btn');

// 当前视图状态
let currentServiceId = null;
let refreshIntervalId = null;
let runtimeIntervalId = null;
const servicesRuntime = {};
let previousView = null;

// 认证状态
let isAuthenticated = false;
let authToken = localStorage.getItem('natter_auth_token');

// API 端点
const API = {
    services: '/api/services',
    service: '/api/service',
    startService: '/api/services/start',
    stopService: '/api/services/stop',
    deleteService: '/api/services/delete',
    restartService: '/api/services/restart',
    stopAllServices: '/api/services/stop-all',
    autoRestart: '/api/services/auto-restart',
    clearLogs: '/api/services/clear-logs',
    templates: '/api/templates',
    saveTemplate: '/api/templates/save',
    deleteTemplate: '/api/templates/delete',
    toolsCheck: '/api/tools/check',
    toolsInstall: '/api/tools/install',
    authCheck: '/api/auth/check',
    authLogin: '/api/auth/login',
    setRemark: '/api/services/set-remark',
    version: '/api/version',
    iyuuConfig: '/api/iyuu/config',
    iyuuUpdate: '/api/iyuu/update',
    iyuuTest: '/api/iyuu/test',
    iyuuAddToken: '/api/iyuu/add_token',
    iyuuDeleteToken: '/api/iyuu/delete_token',
    iyuuPushNow: '/api/iyuu/push_now',
    groups: '/api/groups',
    createGroup: '/api/groups/create',
    deleteGroup: '/api/groups/delete',
    renameGroup: '/api/groups/update',
    moveService: '/api/groups/move-service',
    batchMove: '/api/groups/batch-move',
    updateGroup: '/api/groups/update'
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

// 添加自动重启切换功能
const autoRestartToggle = document.getElementById('auto-restart-toggle');
const autoRestartStatus = document.getElementById('auto-restart-status');

// 检查工具是否已安装
function checkToolInstalled(tool) {
    if (toolsStatus[tool].checking) return;

    toolsStatus[tool].checking = true;

    fetchWithAuth(`${API.toolsCheck}?tool=${tool}`)
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
    iyuuPanel = document.getElementById('iyuu-panel'); // 确保获取IYUU面板
    serviceOutput = document.getElementById('service-output');

    // IYUU相关元素
    iyuuSettingsBtn = document.getElementById('iyuu-settings-btn');
    iyuuEnabled = document.getElementById('iyuu-enabled');
    iyuuTokensList = document.getElementById('iyuu-tokens-list');
    newIyuuToken = document.getElementById('new-iyuu-token');
    addIyuuToken = document.getElementById('add-iyuu-token');
    iyuuScheduleEnabled = document.getElementById('iyuu-schedule-enabled');
    iyuuScheduleTime = document.getElementById('new-schedule-time'); // 调整为新的时间输入框ID
    iyuuScheduleMessage = document.getElementById('iyuu-schedule-message');
    testIyuuPush = document.getElementById('test-iyuu-push');
    saveIyuuSettings = document.getElementById('save-iyuu-settings');
    backFromIyuuBtn = document.getElementById('back-from-iyuu-btn');

    // 分组管理相关元素 - 重新获取确保元素存在
    groupsManagementBtn = document.getElementById('groups-management-btn');
    groupsList = document.getElementById('groups-list');
    newGroupName = document.getElementById('new-group-name');
    addGroupBtn = document.getElementById('add-group-btn');
    batchSourceGroup = document.getElementById('batch-source-group');
    batchTargetGroup = document.getElementById('batch-target-group');
    batchMoveBtn = document.getElementById('batch-move-btn');
    backFromGroupsBtn = document.getElementById('back-from-groups-btn');

    // 新增的IYUU相关元素
    const addScheduleTimeBtn = document.getElementById('add-schedule-time');
    const pushAllServicesBtn = document.getElementById('push-all-services');

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

    // 进行认证检查，只有认证通过才会加载主界面
    checkAuth();

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

                // 对于nftables方法，增加特殊警告
                if (method === 'nftables') {
                    showNotification(`${info.name}: ${info.desc}<br>适用于: ${info.bestFor}<br><span style="color:#ff6b6b;font-weight:bold">⚠️ 警告：在Docker环境中nftables可能不可用。如出现问题，请改用socket或iptables方法。</span>`, 'warning');
                } else {
                    showNotification(`${info.name}: ${info.desc}<br>适用于: ${info.bestFor}`, 'info');
                }

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
        copyAddressBtn.addEventListener('click', function (event) {
            event.stopPropagation(); // 防止事件冒泡
            const address = serviceMappedAddress.textContent;

            // 尝试使用新API
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(address)
                    .then(() => {
                        showCopyFeedback(copyAddressBtn);
                        showNotification('地址已复制: ' + address, 'success');
                    })
                    .catch(err => {
                        console.error('复制失败:', err);
                        showNotification('复制失败，请手动复制', 'error');
                    });
            } else {
                // 回退方法
                try {
                    const tempInput = document.createElement('input');
                    tempInput.value = address;
                    document.body.appendChild(tempInput);
                    tempInput.select();
                    document.execCommand('copy');
                    document.body.removeChild(tempInput);

                    showCopyFeedback(copyAddressBtn);
                    showNotification('地址已复制: ' + address, 'success');
                } catch (err) {
                    console.error('复制失败:', err);
                    showNotification('复制失败，请手动复制', 'error');
                }
            }
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

    // 分组密码编辑对话框按钮事件监听器
    const confirmEditPasswordBtn = document.getElementById('confirm-edit-password');
    const cancelEditPasswordBtn = document.getElementById('cancel-edit-password');

    if (confirmEditPasswordBtn) {
        confirmEditPasswordBtn.addEventListener('click', function () {
            confirmEditPassword();
        });
    }

    if (cancelEditPasswordBtn) {
        cancelEditPasswordBtn.addEventListener('click', function () {
            cancelEditPassword();
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

    // 添加登出按钮事件监听
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', function () {
            logout();
        });
    }

    // 检查认证状态
    checkAuthRequired();

    // 检查Docker环境并显示nftables警告
    checkDockerEnvironment();

    // 添加自动重启切换功能
    if (autoRestartToggle) {
        autoRestartToggle.addEventListener('change', function () {
            const enabled = this.checked;
            toggleAutoRestart(currentServiceId, enabled);
            autoRestartStatus.textContent = enabled ? '已启用' : '已禁用';

            // 添加状态样式类
            autoRestartStatus.className = enabled ? 'status-enabled' : 'status-disabled';
        });
    }

    // 获取版本号
    fetchVersion();

    // IYUU相关
    if (iyuuSettingsBtn) {
        iyuuSettingsBtn.addEventListener('click', function () {
            showIyuuPanel();
        });
    }

    if (backFromIyuuBtn) {
        backFromIyuuBtn.addEventListener('click', function () {
            hideIyuuPanel();
        });
    }

    if (saveIyuuSettings) {
        saveIyuuSettings.addEventListener('click', function () {
            saveIyuuConfig();
        });
    }

    if (testIyuuPush) {
        testIyuuPush.addEventListener('click', function () {
            testIyuuPushMessage(); // 改名以避免与变量冲突
        });
    }

    if (addIyuuToken) {
        addIyuuToken.addEventListener('click', function () {
            addIyuuTokenAction(); // 改名以避免与变量冲突
        });
    }

    if (iyuuScheduleEnabled) {
        iyuuScheduleEnabled.addEventListener('change', function () {
            document.getElementById('iyuu-schedule-options').style.display =
                this.checked ? 'block' : 'none';
        });
    }

    // 添加时间段按钮事件
    if (addScheduleTimeBtn) {
        addScheduleTimeBtn.addEventListener('click', function () {
            addScheduleTime();
        });
    }

    // 立即推送所有服务状态按钮事件
    if (pushAllServicesBtn) {
        pushAllServicesBtn.addEventListener('click', function () {
            pushServicesNow();
        });
    }

    // 分组管理相关事件监听器
    if (groupsManagementBtn) {
        groupsManagementBtn.addEventListener('click', function () {
            showGroupsPanel();
        });
        console.log('分组管理按钮事件监听器已绑定');
    } else {
        console.error('找不到分组管理按钮元素');
    }

    if (addGroupBtn) {
        addGroupBtn.addEventListener('click', function () {
            console.log('添加分组按钮被点击');
            createGroup();
        });
        console.log('添加分组按钮事件监听器已绑定');
    } else {
        console.error('找不到添加分组按钮元素');
    }

    if (batchMoveBtn) {
        batchMoveBtn.addEventListener('click', function () {
            batchMoveServices();
        });
        console.log('批量移动按钮事件监听器已绑定');
    } else {
        console.error('找不到批量移动按钮元素');
    }

    // 添加源分组选择change事件监听器
    if (batchSourceGroup) {
        batchSourceGroup.addEventListener('change', function () {
            updateBatchSourcePreview();
        });
    }

    // 添加目标分组选择change事件监听器
    if (batchTargetGroup) {
        batchTargetGroup.addEventListener('change', function () {
            updateBatchTargetPreview();
        });
    }

    if (backFromGroupsBtn) {
        backFromGroupsBtn.addEventListener('click', function () {
            hideGroupsPanel();
        });
        console.log('返回按钮事件监听器已绑定');
    } else {
        console.error('找不到返回按钮元素');
    }

    // 加载分组列表到服务创建表单中
    loadGroupsForSelect();
});

// 加载服务列表
function loadServices() {
    fetchWithAuth(API.services)
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
    const servicesList = document.getElementById('services-list');
    servicesList.innerHTML = '';

    if (!services || services.length === 0) {
        servicesList.innerHTML = '<div class="empty-services-message">没有运行中的服务</div>';
        return;
    }

    // 获取模板
    const template = document.getElementById('service-card-template');

    services.forEach(service => {
        // 克隆模板
        const card = document.importNode(template.content, true);
        const serviceCard = card.querySelector('.service-card');

        // 设置服务ID
        serviceCard.dataset.id = service.id;
        serviceCard.dataset.status = service.status === '运行中' ? 'running' : 'stopped';

        // 填充服务名称和状态
        const remarkDisplay = card.querySelector('.service-remark-display');
        remarkDisplay.textContent = service.remark || `服务 ${service.id}`;

        const statusElement = card.querySelector('.service-status');
        statusElement.textContent = service.status;
        statusElement.className = `service-status service-status-${service.status === '运行中' ? 'running' : 'stopped'}`;

        // 填充映射地址
        const addressElement = card.querySelector('.service-address');
        const mappedAddress = service.mapped_address || '未映射';
        addressElement.textContent = mappedAddress;

        // 设置快速跳转按钮
        const quickJumpBtn = card.querySelector('.quick-jump-btn');
        if (mappedAddress && mappedAddress !== '未映射' && mappedAddress.includes(':')) {
            quickJumpBtn.style.display = 'inline-block';
            quickJumpBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                const url = mappedAddress.startsWith('http') ? mappedAddress : `http://${mappedAddress}`;
                window.open(url, '_blank');
            });
        } else {
            quickJumpBtn.style.display = 'none';
        }

        // 设置复制地址按钮
        const copyBtn = card.querySelector('.copy-address-btn');
        copyBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            copyToClipboard(mappedAddress, copyBtn);
        });

        // 设置快速状态信息
        const lanStatusEl = card.querySelector('.lan-status');
        const wanStatusEl = card.querySelector('.wan-status');
        const runtimeEl = card.querySelector('.runtime');

        if (lanStatusEl) {
            lanStatusEl.textContent = service.lan_status || '未知';
            setStatusColor(lanStatusEl, service.lan_status);
        }

        if (wanStatusEl) {
            wanStatusEl.textContent = service.wan_status || '未知';
            setStatusColor(wanStatusEl, service.wan_status);
        }

        if (runtimeEl) {
            if (service.start_time && service.status === '运行中') {
                const runtime = formatRuntime(Date.now() / 1000 - service.start_time);
                runtimeEl.textContent = runtime;
            } else {
                runtimeEl.textContent = service.status === '运行中' ? '计算中' : '已停止';
            }
        }

        // 设置分组信息
        const groupText = card.querySelector('.service-group-text');
        groupText.textContent = service.group_name || '默认分组';

        // 设置命令信息
        const cmdText = card.querySelector('.service-cmd-text');
        cmdText.textContent = service.cmd_args ? service.cmd_args.join(' ') : '未知';

        // 添加事件监听器
        card.querySelector('.service-detail-btn').addEventListener('click', () => {
            showServiceDetails(service.id);
        });

        // 快速状态查看按钮
        card.querySelector('.service-quick-status-btn').addEventListener('click', (e) => {
            e.stopPropagation();
            showQuickStatusView(service);
        });

        // 快速重启按钮
        card.querySelector('.service-restart-btn').addEventListener('click', (e) => {
            e.stopPropagation();
            restartService(service.id);
        });

        // 停止按钮
        card.querySelector('.service-stop-btn').addEventListener('click', (e) => {
            e.stopPropagation();
            stopService(service.id);
        });

        // 删除按钮
        card.querySelector('.service-delete-btn').addEventListener('click', (e) => {
            e.stopPropagation();
            deleteService(service.id);
        });

        // 添加到列表
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

    // 新增: 获取目标IP地址
    let targetIpValue = targetIp.value.trim();
    if (targetIpValue) {
        args.push('-t', targetIpValue); // 假设 -t 是目标地址参数
    }
    // 注意: 这里没有添加默认的 127.0.0.1，假设 natter.py 在没有 -t 参数时默认就是本地

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
    let remark = document.getElementById('service-remark')?.value || "";
    let group_id = serviceGroup?.value || "";

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
    fetchWithAuth(API.startService, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                args: args,
                auto_restart: auto_restart,
                remark: remark,
                group_id: group_id
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.service_id) {
                alert('服务启动成功！');
                loadServices();

                // 重置表单
                newServiceForm.reset();
                // 手动清空 targetIp，因为 reset 可能对后面添加的字段无效
                if (targetIp) targetIp.value = '';

                // 重新加载分组选择框
                loadGroupsForSelect();
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

    fetchWithAuth(API.stopService, {
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

    fetchWithAuth(API.restartService, {
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

    fetchWithAuth(API.stopAllServices, {
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
    fetchWithAuth(API.autoRestart, {
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
    fetchWithAuth(API.clearLogs, {
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
    if (refreshIntervalId) {
        clearInterval(refreshIntervalId);
    }

    // 检查当前是否在服务详情页面，如果不在则不更新
    const detailsPanel = document.getElementById('service-details-panel');
    if (!detailsPanel || detailsPanel.style.display === 'none') {
        return;
    }

    fetchWithAuth(`${API.service}?id=${id}`)
        .then(response => response.json())
        .then(data => {
            if (data.service) {
                // 再次检查，确保在异步加载过程中用户没有切换页面
                if (detailsPanel && detailsPanel.style.display !== 'none') {
                    updateServiceDetailsPanel(data.service);
                }
            } else {
                showNotification('加载服务详情失败', 'error');
            }
        })
        .catch(error => {
            console.error('获取服务详情出错:', error);
            showNotification('获取服务详情时发生错误', 'error');
        });
}

// 显示服务详情面板
function showServiceDetailsPanel(service) {
    hideAllPanels();

    // 存储当前服务数据供其他函数使用
    window.currentServiceData = service;

    // 显示面板
    const detailsPanel = document.getElementById('service-details-panel');
    detailsPanel.style.display = 'block';

    // 填充数据
    document.querySelectorAll('#service-id').forEach(el => el.textContent = service.id);
    document.getElementById('service-status').textContent = service.status;
    document.getElementById('service-mapped-address').textContent = service.mapped_address || '未映射';
    document.getElementById('service-cmd-args').textContent = service.cmd_args.join(' ');

    // 设置备注区域
    const debugRemarkArea = document.getElementById('remark-debug-area');
    if (debugRemarkArea) {
        debugRemarkArea.value = service.remark || '';
    }

    // 加载分组选项并设置当前分组
    loadGroupsForServiceDetail(service.group_id);

    // 添加备注保存按钮事件监听
    replaceButtonAndAddListener('save-debug-remark-btn', function (event) {
        event.preventDefault();
        if (debugRemarkArea) {
            const debugValue = debugRemarkArea.value;
            console.log('获取备注值:', debugValue);
            saveServiceRemark(service.id, debugValue);
        }
    });

    // 添加分组保存按钮事件监听
    replaceButtonAndAddListener('save-service-group-btn', function (event) {
        event.preventDefault();
        const groupSelect = document.getElementById('service-group-select');
        if (groupSelect) {
            const newGroupId = groupSelect.value;
            saveServiceGroup(service.id, newGroupId);
        }
    });

    // 添加推送单个服务状态按钮事件监听
    replaceButtonAndAddListener('push-service-now', function (event) {
        event.preventDefault();
        pushServiceNow(service.id);
    });

    // 设置状态文本和样式
    serviceStatus.textContent = service.status;
    setStatusColor(serviceStatus, service.status);

    // 设置映射地址
    serviceMappedAddress.textContent = service.mapped_address || '未映射';

    // 设置命令参数
    serviceCmdArgs.textContent = service.cmd_args.join(' ');

    // 设置运行时间并启动定时更新
    updateDetailPanelRuntime(service);
    if (runtimeIntervalId) {
        clearInterval(runtimeIntervalId);
    }
    runtimeIntervalId = setInterval(() => {
        updateDetailPanelRuntime(service);
    }, 1000);

    // 更新详情标签中的LAN/WAN状态和NAT类型
    lanStatus.textContent = service.lan_status || '未知';
    wanStatus.textContent = service.wan_status || '未知';
    natType.textContent = service.nat_type || '未知';

    // 设置LAN/WAN状态颜色
    setStatusColor(lanStatus, service.lan_status);
    setStatusColor(wanStatus, service.wan_status);

    // 更新状态面板中的可用性信息
    const statusPanelLanStatus = document.querySelector('.status-panel #lan-status');
    const statusPanelWanStatus = document.querySelector('.status-panel #wan-status');
    const statusPanelNatType = document.querySelector('.status-panel #nat-type');

    if (statusPanelLanStatus) {
        statusPanelLanStatus.textContent = service.lan_status || '未知';
        setStatusColor(statusPanelLanStatus, service.lan_status);
    }

    if (statusPanelWanStatus) {
        statusPanelWanStatus.textContent = service.wan_status || '未知';
        setStatusColor(statusPanelWanStatus, service.wan_status);
    }

    if (statusPanelNatType) {
        statusPanelNatType.textContent = service.nat_type || '未知';
    }

    // 设置自动重启状态
    if (autoRestartToggle) {
        autoRestartToggle.checked = service.auto_restart;
        autoRestartStatus.textContent = service.auto_restart ? '已启用' : '已禁用';

        // 添加状态样式类
        autoRestartStatus.className = service.auto_restart ? 'status-enabled' : 'status-disabled';
    }

    // 显示输出日志
    updateServiceLog(service.last_output);

    // 设置服务详情页标题
    document.querySelector('#service-details-panel h2').textContent =
        `服务详情: ${formatAddressShort(service.mapped_address || '未映射')}`;

    // 如果服务已停止，禁用停止按钮，但启用重启按钮
    if (service.status === '已停止' || !service.running) {
        stopServiceBtn.disabled = true;
        restartServiceBtn.disabled = false; // 允许重启已停止的服务
    } else {
        stopServiceBtn.disabled = false;
        restartServiceBtn.disabled = false;
    }

    // 启动自动刷新
    startDetailRefresh();
}

// 更新服务详情面板内容（不强制显示面板）
function updateServiceDetailsPanel(service) {
    // 存储当前服务数据供其他函数使用
    window.currentServiceData = service;

    // 填充数据
    document.querySelectorAll('#service-id').forEach(el => el.textContent = service.id);
    document.getElementById('service-status').textContent = service.status;
    document.getElementById('service-mapped-address').textContent = service.mapped_address || '未映射';
    document.getElementById('service-cmd-args').textContent = service.cmd_args.join(' ');

    // 设置备注区域
    const debugRemarkArea = document.getElementById('remark-debug-area');
    if (debugRemarkArea) {
        debugRemarkArea.value = service.remark || '';
    }

    // 设置状态文本和样式
    serviceStatus.textContent = service.status;
    setStatusColor(serviceStatus, service.status);

    // 设置映射地址
    serviceMappedAddress.textContent = service.mapped_address || '未映射';

    // 设置命令参数
    serviceCmdArgs.textContent = service.cmd_args.join(' ');

    // 更新详情标签中的LAN/WAN状态和NAT类型
    lanStatus.textContent = service.lan_status || '未知';
    wanStatus.textContent = service.wan_status || '未知';
    natType.textContent = service.nat_type || '未知';

    // 设置LAN/WAN状态颜色
    setStatusColor(lanStatus, service.lan_status);
    setStatusColor(wanStatus, service.wan_status);

    // 更新状态面板中的可用性信息
    const statusPanelLanStatus = document.querySelector('.status-panel #lan-status');
    const statusPanelWanStatus = document.querySelector('.status-panel #wan-status');
    const statusPanelNatType = document.querySelector('.status-panel #nat-type');

    if (statusPanelLanStatus) {
        statusPanelLanStatus.textContent = service.lan_status || '未知';
        setStatusColor(statusPanelLanStatus, service.lan_status);
    }

    if (statusPanelWanStatus) {
        statusPanelWanStatus.textContent = service.wan_status || '未知';
        setStatusColor(statusPanelWanStatus, service.wan_status);
    }

    if (statusPanelNatType) {
        statusPanelNatType.textContent = service.nat_type || '未知';
    }

    // 设置自动重启状态
    if (autoRestartToggle) {
        autoRestartToggle.checked = service.auto_restart;
        autoRestartStatus.textContent = service.auto_restart ? '已启用' : '已禁用';

        // 添加状态样式类
        autoRestartStatus.className = service.auto_restart ? 'status-enabled' : 'status-disabled';
    }

    // 显示输出日志
    updateServiceLog(service.last_output);

    // 设置服务详情页标题
    document.querySelector('#service-details-panel h2').textContent =
        `服务详情: ${formatAddressShort(service.mapped_address || '未映射')}`;

    // 如果服务已停止，禁用停止按钮，但启用重启按钮
    if (service.status === '已停止' || !service.running) {
        stopServiceBtn.disabled = true;
        restartServiceBtn.disabled = false; // 允许重启已停止的服务
    } else {
        stopServiceBtn.disabled = false;
        restartServiceBtn.disabled = false;
    }
}

// 辅助函数：替换按钮并添加新的事件监听器
function replaceButtonAndAddListener(buttonId, clickHandler) {
    const button = document.getElementById(buttonId);
    if (!button) return;

    // 创建新按钮并复制属性
    const newButton = document.createElement('button');
    newButton.id = buttonId;
    newButton.className = button.className;
    newButton.textContent = button.textContent;

    // 添加事件监听器
    newButton.addEventListener('click', clickHandler);

    // 替换原按钮
    button.parentNode.replaceChild(newButton, button);
}

// 保存服务备注 - 简化并完全重构
function saveServiceRemark(serviceId, remark) {
    // 强制转换为字符串并进行简单清理
    const remarkValue = String(remark || '').trim();

    console.log('准备保存备注 - 服务ID:', serviceId);
    console.log('准备保存备注 - 最终值:', remarkValue);

    fetchWithAuth(API.setRemark, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                id: serviceId,
                remark: remarkValue
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification('备注已保存: ' + remarkValue, 'success');

                // 更新所有显示和跟踪的值
                updateAllRemarkDisplays(serviceId, remarkValue);

                // 刷新服务列表
                loadServices();
            } else {
                showNotification('保存备注失败：' + (data.error || '未知错误'), 'error');
            }
        })
        .catch(error => {
            console.error('保存备注出错:', error);
            showNotification('保存备注时发生错误', 'error');
        });
}

// 更新所有备注显示
function updateAllRemarkDisplays(serviceId, remarkValue) {
    // 更新备用输入区域
    const debugRemarkArea = document.getElementById('remark-debug-area');
    if (debugRemarkArea) {
        debugRemarkArea.value = remarkValue;
    }

    // 更新当前服务数据
    if (window.currentServiceData && currentServiceId === serviceId) {
        window.currentServiceData.remark = remarkValue;
    }

    console.log('所有备注显示已更新为:', remarkValue);
}

// 设置状态显示的颜色
function setStatusColor(element, status) {
    // 清除之前的状态类
    element.classList.remove('status-good', 'status-warning', 'status-error', 'status-info');

    if (status === 'OPEN' || status === '可达' || status === '正常') {
        element.classList.add('status-good');
    } else if (status === 'CLOSED' || status === '不可达' || status === '错误') {
        element.classList.add('status-error');
    } else if (status === 'UNKNOWN' || status === '未知' || status === '检测中') {
        element.classList.add('status-warning');
    } else {
        element.classList.add('status-info');
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
    fetchWithAuth(API.templates)
        .then(response => response.json())
        .then(data => {
            renderTemplatesList(data.templates);
        })
        .catch(error => {
            console.error('加载模板列表出错:', error);
            templatesList.innerHTML = '<div class="no-services">没有保存的模板。</div>';
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

    fetchWithAuth(API.deleteTemplate, {
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
        fetchWithAuth(`${API.service}?id=${serviceId}`)
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
    fetchWithAuth(API.saveTemplate, {
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
function copyToClipboard(text, button) {
    if (!text || text === '等待映射...' || text === '未知') {
        showNotification('暂无可复制的地址', 'warning');
        return;
    }

    // 如果没有传入button参数，尝试从事件中获取
    if (!button && event) {
        button = event.currentTarget;
    }

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

// 显示复制成功的视觉反馈
function showCopyFeedback(button) {
    if (!button) return;

    // 保存原始文本
    const originalText = button.textContent;
    const originalHTML = button.innerHTML;

    // 修改按钮文本和样式
    button.innerHTML = '<i class="icon-check"></i> 已复制！';
    button.classList.add('copy-success');

    // 恢复原始状态
    setTimeout(() => {
        button.innerHTML = originalHTML;
        button.classList.remove('copy-success');
    }, 1500);
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

/**
 * 删除指定的服务
 * @param {string} id - 服务ID
 */
function deleteService(id) {
    fetchWithAuth(API.deleteService, {
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
function showNotification(message, type = 'info', duration = 5000) {
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
            if (document.body.contains(notification)) {
                document.body.removeChild(notification);
            }
        }, 300);
    }, duration); // 使用传入的持续时间
}

/**
 * 安装指定工具
 * @param {string} tool - 工具名称
 */
function installTool(tool) {
    showNotification(`正在安装 ${tool}，请稍候...`, 'info');

    fetchWithAuth(API.toolsInstall, {
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

// 添加登录表单HTML
function createLoginForm() {
    // 直接重定向到登录页面
    window.location.href = 'login.html';
}

// 检查是否需要认证
function checkAuthRequired() {
    return fetchWithAuth(API.authCheck)
        .then(response => {
            // 检查响应状态
            if (!response.ok) {
                // 如果响应不成功（例如500错误），视为配置加载失败
                console.error('配置加载失败，重定向到登录页面');
                window.location.href = 'login.html';
                // 抛出错误终止后续处理
                throw new Error('配置加载失败');
            }
            return response.json();
        })
        .then(data => {
            const authRequired = data.auth_required;
            const authenticated = data.authenticated;

            console.log('认证检查结果:', {
                authRequired,
                authenticated,
                hasToken: !!authToken
            });

            if (authRequired) {
                // 如果需要认证
                if (!authenticated && !authToken) {
                    // 未认证且无token，重定向到登录页面
                    console.log('需要认证但未登录，重定向到登录页面');
                    window.location.href = 'login.html';
                    return;
                } else if (authenticated || authToken) {
                    // 已认证或有token，显示管理员功能
                    console.log('管理员已认证，显示管理员功能按钮');
                    isAuthenticated = true;

                    // 显示退出登录按钮
                    const logoutBtn = document.getElementById('logout-btn');
                    if (logoutBtn) {
                        logoutBtn.style.display = 'inline-flex';
                        console.log('显示退出登录按钮');
                    }

                    // 显示IYUU推送设置按钮
                    const iyuuSettingsBtn = document.getElementById('iyuu-settings-btn');
                    if (iyuuSettingsBtn) {
                        iyuuSettingsBtn.style.display = 'inline-flex';
                        console.log('显示IYUU推送设置按钮');
                    }

                    showServicesList();
                }
            } else {
                // 不需要认证，但仍然显示功能按钮
                console.log('不需要认证，显示功能按钮');
                isAuthenticated = true;

                // 如果用户已认证，显示退出按钮
                const token = localStorage.getItem('natter_auth_token');
                const logoutBtn = document.getElementById('logout-btn');
                if (logoutBtn) {
                    if (token && authenticated) {
                        logoutBtn.style.display = 'inline-flex';
                        console.log('显示退出登录按钮（用户已认证但系统不强制要求认证）');
                    } else {
                        logoutBtn.style.display = 'none';
                    }
                }

                // 显示IYUU推送设置按钮（即使不需要认证也可以使用推送功能）
                const iyuuSettingsBtn = document.getElementById('iyuu-settings-btn');
                if (iyuuSettingsBtn) {
                    iyuuSettingsBtn.style.display = 'inline-flex';
                    console.log('显示IYUU推送设置按钮（无认证模式）');
                }

                showServicesList();
            }
            return authRequired;
        })
        .catch(error => {
            console.error('检查认证状态时出错:', error);
            // 出错时重定向到登录页面
            window.location.href = 'login.html';
            return true; // 默认需要认证
        });
}

// 登录功能 - 现在已不需要，登录在login.html中处理
function login(password) {
    // 这个函数现在不再使用，因为登录已移至login.html
    // 保留此函数以避免可能的引用错误
    console.warn('login函数不再使用，请使用login.html进行登录');
    return Promise.reject(new Error('请使用login.html进行登录'));
}

// 登出功能
function logout() {
    authToken = null;
    isAuthenticated = false;
    localStorage.removeItem('natter_auth_token');

    // 跳转到统一登录页面
    window.location.href = '/login.html';
}

// 隐藏所有面板
function hideAllPanels() {
    servicesPanel.style.display = 'none';
    newServicePanel.style.display = 'none';

    // 如果隐藏服务详情面板，清理相关定时器
    if (serviceDetailsPanel.style.display !== 'none') {
        if (refreshIntervalId) {
            clearInterval(refreshIntervalId);
            refreshIntervalId = null;
        }
        if (runtimeIntervalId) {
            clearInterval(runtimeIntervalId);
            runtimeIntervalId = null;
        }
    }

    serviceDetailsPanel.style.display = 'none';
    helpPanel.style.display = 'none';
    templatesPanel.style.display = 'none';
    iyuuPanel.style.display = 'none';
    groupsPanel.style.display = 'none';
}

// 添加Authorization头到fetch请求
function fetchWithAuth(url, options = {}) {
    // 深复制选项，避免修改原对象
    const newOptions = JSON.parse(JSON.stringify(options));

    // 确保headers对象存在
    newOptions.headers = newOptions.headers || {};

    // 每次都从localStorage中读取最新的token
    const currentToken = localStorage.getItem('natter_auth_token');

    // 添加认证头（如果有token）
    if (currentToken) {
        newOptions.headers['Authorization'] = `Bearer ${currentToken}`;
    }

    return fetch(url, newOptions)
        .then(response => {
            // 对于401响应，先检查是否是API认证错误信息
            if (response.status === 401) {
                // 先复制响应，以便能够多次读取内容
                const responseClone = response.clone();

                // 尝试解析JSON响应
                return responseClone.json()
                    .then(data => {
                        // 如果包含auth_required字段，则正常返回响应
                        if (data.auth_required) {
                            return response;
                        } else {
                            // 否则执行登出
                            logout();
                            throw new Error('认证失败，请重新登录');
                        }
                    })
                    .catch(() => {
                        // 如果无法解析JSON，则执行登出
                        logout();
                        throw new Error('认证失败，请重新登录');
                    });
            }
            return response;
        });
}

// 添加新函数，用于检查Docker环境
function checkDockerEnvironment() {
    // 由于前端无法直接检测Docker环境，我们假设在Docker中运行
    // 因为这个应用主要设计为在Docker中使用

    // 获取nftables选项
    const nftablesOption = document.querySelector('option[value="nftables"]');

    if (nftablesOption && nftablesOption.disabled) {
        // 如果已禁用，显示全局通知
        showNotification(`
            <strong>注意：</strong> 检测到Docker容器环境，已禁用nftables转发方法。<br>
            Docker容器缺少运行nftables所需的内核权限。<br>
            请使用<strong>socket</strong>或<strong>iptables</strong>转发方法。
        `, 'warning', 10000); // 显示10秒
    }
}

// 切换服务的自动重启功能
function toggleAutoRestart(serviceId, enabled) {
    fetchWithAuth(API.autoRestart, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                id: serviceId,
                enabled: enabled
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification(`服务自动重启已${enabled ? '启用' : '禁用'}`, 'success');
                // 更新状态样式类
                if (autoRestartStatus) {
                    autoRestartStatus.className = enabled ? 'status-enabled' : 'status-disabled';
                }
            } else {
                showNotification('设置自动重启失败', 'error');
                // 回滚UI状态
                if (autoRestartToggle) {
                    autoRestartToggle.checked = !enabled;
                }
                if (autoRestartStatus) {
                    autoRestartStatus.textContent = !enabled ? '已启用' : '已禁用';
                    autoRestartStatus.className = !enabled ? 'status-enabled' : 'status-disabled';
                }
            }
        })
        .catch(error => {
            console.error('设置自动重启出错:', error);
            showNotification('设置自动重启时发生错误', 'error');
            // 回滚UI状态
            if (autoRestartToggle) {
                autoRestartToggle.checked = !enabled;
            }
            if (autoRestartStatus) {
                autoRestartStatus.textContent = !enabled ? '已启用' : '已禁用';
                autoRestartStatus.className = !enabled ? 'status-enabled' : 'status-disabled';
            }
        });
}

// 更新服务详情面板的运行时间
function updateDetailPanelRuntime(service) {
    if (!service.start_time) {
        serviceRuntime.textContent = 'N/A';
        return;
    }

    const runtime = formatRuntime(Date.now() / 1000 - service.start_time);
    serviceRuntime.textContent = runtime;
}

// 更新服务日志
function updateServiceLog(logs) {
    // 更新输出日志，限制最多显示100条
    let outputLines = logs || [];
    if (outputLines.length > 100) {
        // 只保留最新的100条日志
        outputLines = outputLines.slice(-100);
        serviceOutput.textContent = `[显示最新100条日志，共${logs.length}条]\n` + outputLines.join('\n');
    } else {
        serviceOutput.textContent = outputLines.join('\n');
    }

    if (autoScroll && autoScroll.checked) {
        serviceOutput.scrollTop = serviceOutput.scrollHeight;
    }
}

// 启动服务详情自动刷新
function startDetailRefresh() {
    // 清除现有的刷新定时器
    if (refreshIntervalId) {
        clearInterval(refreshIntervalId);
    }

    // 设置新的刷新定时器，每5秒刷新一次服务详情
    refreshIntervalId = setInterval(() => {
        if (currentServiceId) {
            loadServiceDetails(currentServiceId);
        } else {
            // 如果没有当前服务ID，停止刷新
            clearInterval(refreshIntervalId);
            refreshIntervalId = null;
        }
    }, 5000);
}

// 获取版本号
function fetchVersion() {
    fetch(API.version)
        .then(response => response.json())
        .then(data => {
            document.getElementById('version').textContent = data.version;
        })
        .catch(error => {
            console.error('获取版本号失败:', error);
            document.getElementById('version').textContent = '未知';
        });
}

// 显示IYUU设置面板
function showIyuuPanel() {
    previousView = {
        servicesPanel: servicesPanel.style.display,
        newServicePanel: newServicePanel.style.display,
        serviceDetailsPanel: serviceDetailsPanel.style.display,
        helpPanel: helpPanel.style.display,
        templatesPanel: templatesPanel.style.display
    };

    // 隐藏其他面板
    hideAllPanels();

    // 显示IYUU面板
    iyuuPanel.style.display = 'block';

    // 加载IYUU配置
    loadIyuuConfig();
}

// 隐藏IYUU设置面板
function hideIyuuPanel() {
    iyuuPanel.style.display = 'none';

    if (previousView) {
        servicesPanel.style.display = previousView.servicesPanel;
        newServicePanel.style.display = previousView.newServicePanel;
        serviceDetailsPanel.style.display = previousView.serviceDetailsPanel;
        helpPanel.style.display = previousView.helpPanel;
        templatesPanel.style.display = previousView.templatesPanel;
    } else {
        showServicesList();
    }
}

// 加载IYUU配置
function loadIyuuConfig() {
    fetchWithAuth(API.iyuuConfig)
        .then(response => response.json())
        .then(data => {
            if (data.config) {
                const config = data.config;

                // 设置启用状态
                iyuuEnabled.checked = config.enabled;

                // 加载令牌列表
                renderIyuuTokens(config.tokens || []);

                // 设置定时推送配置
                const schedule = config.schedule || {};
                iyuuScheduleEnabled.checked = schedule.enabled || false;
                iyuuScheduleMessage.value = schedule.message || "Natter服务状态日报";

                // 渲染时间段列表
                renderScheduleTimes(schedule.times || ["08:00"]);

                // 根据定时推送状态显示或隐藏选项
                document.getElementById('iyuu-schedule-options').style.display =
                    schedule.enabled ? 'block' : 'none';
            }
        })
        .catch(error => {
            console.error('加载IYUU配置出错:', error);
            showNotification('加载IYUU配置失败', 'error');
        });
}

// 渲染定时推送时间段列表
function renderScheduleTimes(times) {
    const timesList = document.getElementById('schedule-times-list');
    timesList.innerHTML = '';

    if (!times || times.length === 0) {
        timesList.innerHTML = '<div class="empty-tokens">未添加任何时间段</div>';
        return;
    }

    times.forEach(time => {
        const timeItem = document.createElement('div');
        timeItem.className = 'schedule-time-item';

        const timeText = document.createElement('span');
        timeText.className = 'time-text';
        timeText.textContent = time;

        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'btn-danger btn-small';
        deleteBtn.textContent = '删除';
        deleteBtn.addEventListener('click', function () {
            removeScheduleTime(time);
        });

        timeItem.appendChild(timeText);
        timeItem.appendChild(deleteBtn);
        timesList.appendChild(timeItem);
    });
}

// 添加时间段
function addScheduleTime() {
    const newTimeInput = document.getElementById('new-schedule-time');
    const newTime = newTimeInput.value.trim();

    if (!newTime) {
        showNotification('请选择有效的时间', 'warning');
        return;
    }

    // 获取当前配置中的时间段列表
    fetchWithAuth(API.iyuuConfig)
        .then(response => response.json())
        .then(data => {
            if (data.config) {
                const config = data.config;
                const schedule = config.schedule || {};
                const times = schedule.times || [];

                // 检查是否已存在相同时间
                if (times.includes(newTime)) {
                    showNotification('该时间段已存在', 'warning');
                    return;
                }

                // 添加新时间段
                times.push(newTime);

                // 更新配置
                const updatedConfig = {
                    enabled: config.enabled,
                    schedule: {
                        enabled: schedule.enabled,
                        times: times,
                        message: schedule.message
                    }
                };

                // 保存更新后的配置
                saveIyuuConfigWithData(updatedConfig);

                // 清空输入框
                newTimeInput.value = '08:00';
            }
        })
        .catch(error => {
            console.error('获取IYUU配置出错:', error);
            showNotification('获取IYUU配置失败', 'error');
        });
}

// 移除时间段
function removeScheduleTime(time) {
    if (!confirm('确定要删除此时间段吗？')) {
        return;
    }

    // 获取当前配置
    fetchWithAuth(API.iyuuConfig)
        .then(response => response.json())
        .then(data => {
            if (data.config) {
                const config = data.config;
                const schedule = config.schedule || {};
                let times = schedule.times || [];

                // 移除指定时间段
                times = times.filter(t => t !== time);

                // 更新配置
                const updatedConfig = {
                    enabled: config.enabled,
                    schedule: {
                        enabled: schedule.enabled,
                        times: times,
                        message: schedule.message
                    }
                };

                // 保存更新后的配置
                saveIyuuConfigWithData(updatedConfig);
            }
        })
        .catch(error => {
            console.error('获取IYUU配置出错:', error);
            showNotification('获取IYUU配置失败', 'error');
        });
}

// 使用指定数据保存IYUU配置
function saveIyuuConfigWithData(config) {
    fetchWithAuth(API.iyuuUpdate, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(config)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification('IYUU配置已保存', 'success');
                loadIyuuConfig(); // 重新加载确认配置已更新
            } else {
                showNotification('保存IYUU配置失败', 'error');
            }
        })
        .catch(error => {
            console.error('保存IYUU配置出错:', error);
            showNotification('保存IYUU配置时发生错误', 'error');
        });
}

// 修改保存IYUU配置函数，支持多时间段
function saveIyuuConfig() {
    // 收集当前配置
    const config = {
        enabled: iyuuEnabled.checked,
        schedule: {
            enabled: iyuuScheduleEnabled.checked,
            message: iyuuScheduleMessage.value
        }
    };

    // 获取当前配置中的时间段列表
    fetchWithAuth(API.iyuuConfig)
        .then(response => response.json())
        .then(data => {
            if (data.config) {
                const currentConfig = data.config;
                const schedule = currentConfig.schedule || {};

                // 使用当前的时间段列表
                config.schedule.times = schedule.times || ["08:00"];

                // 保存更新后的配置
                saveIyuuConfigWithData(config);
            }
        })
        .catch(error => {
            console.error('获取IYUU配置出错:', error);
            showNotification('获取IYUU配置失败', 'error');
        });
}

// 立即推送当前服务状态
function pushServicesNow() {
    fetchWithAuth(API.iyuuPushNow, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({})
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification('服务状态推送成功', 'success');
            } else {
                showNotification(`推送失败: ${data.errors ? data.errors.join(', ') : '未知错误'}`, 'error');
            }
        })
        .catch(error => {
            console.error('推送服务状态出错:', error);
            showNotification('推送服务状态时发生错误', 'error');
        });
}

// 立即推送指定服务状态
function pushServiceNow(serviceId) {
    fetchWithAuth(API.iyuuPushNow, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                service_id: serviceId
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification('服务状态推送成功', 'success');
            } else {
                showNotification(`推送失败: ${data.errors ? data.errors.join(', ') : '未知错误'}`, 'error');
            }
        })
        .catch(error => {
            console.error('推送服务状态出错:', error);
            showNotification('推送服务状态时发生错误', 'error');
        });
}

// 渲染IYUU令牌列表
function renderIyuuTokens(tokens) {
    const tokensList = document.getElementById('iyuu-tokens-list');
    tokensList.innerHTML = '';

    if (!tokens || tokens.length === 0) {
        tokensList.innerHTML = '<div class="empty-tokens">未添加任何令牌</div>';
        return;
    }

    tokens.forEach(token => {
        const tokenItem = document.createElement('div');
        tokenItem.className = 'token-item';

        const tokenText = document.createElement('span');
        tokenText.className = 'token-text';
        tokenText.textContent = token;

        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'btn-danger btn-small';
        deleteBtn.textContent = '删除';
        deleteBtn.addEventListener('click', function () {
            deleteIyuuToken(token);
        });

        tokenItem.appendChild(tokenText);
        tokenItem.appendChild(deleteBtn);
        tokensList.appendChild(tokenItem);
    });
}

// 删除IYUU令牌
function deleteIyuuToken(token) {
    if (!confirm('确定要删除此令牌吗？')) {
        return;
    }

    fetchWithAuth(API.iyuuDeleteToken, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                token: token
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification(data.message || '令牌已删除', 'success');
                loadIyuuConfig(); // 重新加载令牌列表
            } else {
                showNotification(data.message || '删除令牌失败', 'error');
            }
        })
        .catch(error => {
            console.error('删除IYUU令牌出错:', error);
            showNotification('删除令牌时发生错误', 'error');
        });
}

// 测试IYUU推送（改名避免冲突）
function testIyuuPushMessage() {
    fetchWithAuth(API.iyuuTest)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification('测试消息已成功发送', 'success');
            } else {
                showNotification(`测试消息发送失败: ${data.errors ? data.errors.join(', ') : '未知错误'}`, 'error');
            }
        })
        .catch(error => {
            console.error('测试IYUU推送出错:', error);
            showNotification('测试推送时发生错误', 'error');
        });
}

// 添加IYUU令牌（改名避免冲突）
function addIyuuTokenAction() {
    const token = newIyuuToken.value.trim();

    if (!token) {
        showNotification('请输入有效的IYUU令牌', 'warning');
        return;
    }

    fetchWithAuth(API.iyuuAddToken, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                token: token
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification(data.message || '令牌已添加', 'success');
                newIyuuToken.value = ''; // 清空输入框
                loadIyuuConfig(); // 重新加载令牌列表
            } else {
                showNotification(data.message || '添加令牌失败', 'error');
            }
        })
        .catch(error => {
            console.error('添加IYUU令牌出错:', error);
            showNotification('添加令牌时发生错误', 'error');
        });
}

function checkAuth() {
    const token = localStorage.getItem('natter_auth_token');
    if (!token) {
        // 没有token，跳转到统一登录页面
        window.location.href = '/login.html';
        return false;
    }

    // 验证token有效性
    fetch('/api/auth/check', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.authenticated) {
                // 已认证，显示主界面
                showMainInterface();
            } else {
                // token无效，清除并跳转到登录页面
                localStorage.removeItem('natter_auth_token');
                window.location.href = '/login.html';
            }
        })
        .catch(error => {
            console.error('认证检查失败:', error);
            // 网络错误，也跳转到登录页面
            localStorage.removeItem('natter_auth_token');
            window.location.href = '/login.html';
        });

    return true;
}

// 显示主界面
function showMainInterface() {
    // 显示退出登录按钮（如果用户已认证）
    const token = localStorage.getItem('natter_auth_token');
    if (token) {
        const logoutBtn = document.getElementById('logout-btn');
        if (logoutBtn) {
            logoutBtn.style.display = 'inline-flex';
            console.log('显示退出登录按钮（已认证用户）');
        }

        // 显示IYUU推送设置按钮
        const iyuuSettingsBtn = document.getElementById('iyuu-settings-btn');
        if (iyuuSettingsBtn) {
            iyuuSettingsBtn.style.display = 'inline-flex';
            console.log('显示IYUU推送设置按钮');
        }
    }

    // 加载服务列表
    loadServices();

    // 获取版本号
    fetchVersion();

    // 设置页面刷新定时器 (每10秒刷新一次列表)
    if (!window.refreshTimer) {
        window.refreshTimer = setInterval(loadServices, 10000);
    }
}

// ==================== 分组管理功能 ====================

// 显示分组管理面板
function showGroupsPanel() {
    previousView = {
        servicesPanel: servicesPanel.style.display,
        newServicePanel: newServicePanel.style.display,
        serviceDetailsPanel: serviceDetailsPanel.style.display,
        helpPanel: helpPanel.style.display,
        templatesPanel: templatesPanel.style.display,
        iyuuPanel: iyuuPanel.style.display
    };

    // 隐藏其他面板
    hideAllPanels();

    // 显示分组面板
    groupsPanel.style.display = 'block';

    // 加载分组列表
    loadGroups();
    loadGroupsForBatchOperations();
}

// 隐藏分组管理面板
function hideGroupsPanel() {
    groupsPanel.style.display = 'none';

    if (previousView) {
        servicesPanel.style.display = previousView.servicesPanel;
        newServicePanel.style.display = previousView.newServicePanel;
        serviceDetailsPanel.style.display = previousView.serviceDetailsPanel;
        helpPanel.style.display = previousView.helpPanel;
        templatesPanel.style.display = previousView.templatesPanel;
        iyuuPanel.style.display = previousView.iyuuPanel;
    } else {
        showServicesList();
    }
}

// 加载分组列表
function loadGroups() {
    fetchWithAuth(API.groups)
        .then(response => response.json())
        .then(data => {
            if (data.groups) {
                renderGroupsList(data.groups);
            } else {
                showNotification('加载分组列表失败', 'error');
            }
        })
        .catch(error => {
            console.error('加载分组列表出错:', error);
            groupsList.innerHTML = '<div class="loading">加载分组失败</div>';
        });
}

// 渲染分组列表
function renderGroupsList(groups) {
    if (!groups || groups.length === 0) {
        groupsList.innerHTML = '<div class="empty-services-message">暂无分组</div>';
        return;
    }

    groupsList.innerHTML = '';
    const template = document.getElementById('group-card-template');

    groups.forEach(group => {
        const card = document.importNode(template.content, true);
        const groupCard = card.querySelector('.group-card');

        // 设置分组数据
        groupCard.dataset.groupId = group.id;
        card.querySelector('.group-name').textContent = group.name;
        card.querySelector('.group-service-count').textContent = `${group.service_count || 0} 个服务`;

        // 设置密码显示（需要从后端获取完整的分组信息）
        const passwordValue = card.querySelector('.password-value');
        passwordValue.dataset.password = group.password || '';
        passwordValue.textContent = '••••••••'; // 默认隐藏

        // 渲染服务列表
        const servicesList = card.querySelector('.group-services-list');
        if (group.services && group.services.length > 0) {
            servicesList.innerHTML = '';
            group.services.forEach(service => {
                const serviceItem = document.createElement('div');
                serviceItem.className = 'group-service-item';
                serviceItem.innerHTML = `
                    <span>${formatAddressShort(service.mapped_address || '未映射')}</span>
                    <button class="btn btn-small btn-secondary move-service-btn" 
                            data-service-id="${service.id}" data-current-group="${group.id}">
                        移动
                    </button>
                `;
                servicesList.appendChild(serviceItem);
            });
        } else {
            servicesList.innerHTML = '<div style="color: #666; font-style: italic;">暂无服务</div>';
        }

        // 添加密码相关事件监听器
        const passwordToggleBtn = card.querySelector('.password-toggle-btn');
        const viewPasswordBtn = card.querySelector('.view-password-btn');
        const editPasswordBtn = card.querySelector('.edit-password-btn');

        // 密码显示/隐藏切换
        passwordToggleBtn.addEventListener('click', function () {
            togglePasswordVisibility(passwordValue);
        });

        // 查看密码（快速显示3秒后自动隐藏）
        viewPasswordBtn.addEventListener('click', function () {
            showPasswordTemporarily(passwordValue);
        });

        // 编辑密码
        editPasswordBtn.addEventListener('click', function () {
            editGroupPassword(group.id, group.name, group.password || '');
        });

        // 添加原有事件监听器
        const renameBtn = card.querySelector('.rename-group-btn');
        const deleteBtn = card.querySelector('.delete-group-btn');

        renameBtn.addEventListener('click', function () {
            renameGroup(group.id, group.name);
        });

        deleteBtn.addEventListener('click', function () {
            if (confirm('确定要删除此分组吗？分组中的服务将移动到默认分组。')) {
                deleteGroup(group.id);
            }
        });

        // 为移动按钮添加事件监听器
        card.querySelectorAll('.move-service-btn').forEach(btn => {
            btn.addEventListener('click', function () {
                const serviceId = this.dataset.serviceId;
                const currentGroup = this.dataset.currentGroup;
                showMoveServiceDialog(serviceId, currentGroup);
            });
        });

        groupsList.appendChild(card);
    });
}

// 创建新分组
function createGroup() {
    // 确保DOM元素存在
    const groupNameElement = document.getElementById('new-group-name');
    const groupPasswordElement = document.getElementById('new-group-password');

    if (!groupNameElement) {
        console.error('找不到分组名称输入框元素');
        showNotification('页面元素错误，请刷新页面重试', 'error');
        return;
    }

    if (!groupPasswordElement) {
        console.error('找不到分组密码输入框元素');
        showNotification('页面元素错误，请刷新页面重试', 'error');
        return;
    }

    const groupName = groupNameElement.value.trim();
    const groupPassword = groupPasswordElement.value.trim();

    console.log('创建分组 - 分组名称:', groupName);
    console.log('创建分组 - 密码长度:', groupPassword.length);

    if (!groupName) {
        showNotification('请输入分组名称', 'warning');
        return;
    }

    if (!groupPassword) {
        showNotification('请输入分组密码', 'warning');
        return;
    }

    console.log('发送创建分组请求...');

    fetchWithAuth(API.createGroup, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                name: groupName,
                password: groupPassword
            })
        })
        .then(response => response.json())
        .then(data => {
            console.log('创建分组响应:', data);
            if (data.group_id) {
                showNotification('分组创建成功', 'success');
                groupNameElement.value = '';
                groupPasswordElement.value = '';
                loadGroups();
                loadGroupsForSelect();
                loadGroupsForBatchOperations();
            } else {
                showNotification('创建分组失败：' + (data.error || '未知错误'), 'error');
            }
        })
        .catch(error => {
            console.error('创建分组出错:', error);
            showNotification('创建分组时发生错误', 'error');
        });
}

// 重命名分组
function renameGroup(groupId, currentName) {
    const newName = prompt('请输入新的分组名称:', currentName);

    if (!newName || newName.trim() === '' || newName.trim() === currentName) {
        return;
    }

    fetchWithAuth(API.renameGroup, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                group_id: groupId,
                name: newName.trim()
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification('分组重命名成功', 'success');
                loadGroups();
                loadGroupsForSelect();
                loadGroupsForBatchOperations();
            } else {
                showNotification('重命名分组失败：' + (data.error || '未知错误'), 'error');
            }
        })
        .catch(error => {
            console.error('重命名分组出错:', error);
            showNotification('重命名分组时发生错误', 'error');
        });
}

// 删除分组
function deleteGroup(groupId) {
    fetchWithAuth(API.deleteGroup, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                group_id: groupId
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification('分组删除成功', 'success');
                loadGroups();
                loadGroupsForSelect();
                loadGroupsForBatchOperations();
            } else {
                showNotification('删除分组失败：' + (data.error || '未知错误'), 'error');
            }
        })
        .catch(error => {
            console.error('删除分组出错:', error);
            showNotification('删除分组时发生错误', 'error');
        });
}

// 显示移动服务对话框
function showMoveServiceDialog(serviceId, currentGroupId) {
    // 获取分组列表
    fetchWithAuth(API.groups)
        .then(response => response.json())
        .then(data => {
            if (data.groups) {
                const groups = data.groups;
                let options = '<option value="">默认分组</option>';

                groups.forEach(group => {
                    if (group.id !== currentGroupId) {
                        options += `<option value="${group.id}">${group.name}</option>`;
                    }
                });

                const targetGroup = prompt(`请选择目标分组:\n\n可用分组:\n${groups.filter(g => g.id !== currentGroupId).map(g => `- ${g.name}`).join('\n')}\n- 默认分组\n\n请输入分组名称(输入"默认"表示移动到默认分组):`);

                if (targetGroup !== null) {
                    let targetGroupId = '';

                    if (targetGroup.trim() === '默认' || targetGroup.trim() === '') {
                        targetGroupId = '';
                    } else {
                        const foundGroup = groups.find(g => g.name === targetGroup.trim());
                        if (foundGroup) {
                            targetGroupId = foundGroup.id;
                        } else {
                            showNotification('未找到指定的分组', 'warning');
                            return;
                        }
                    }

                    moveServiceToGroup(serviceId, targetGroupId);
                }
            }
        })
        .catch(error => {
            console.error('获取分组列表出错:', error);
            showNotification('获取分组列表失败', 'error');
        });
}

// 移动服务到指定分组
function moveServiceToGroup(serviceId, targetGroupId) {
    fetchWithAuth(API.moveService, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                service_id: serviceId,
                group_id: targetGroupId || ''
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification('服务移动成功', 'success');
                loadGroups();
                loadServices(); // 刷新主界面的服务列表
            } else {
                showNotification('移动服务失败：' + (data.error || '未知错误'), 'error');
            }
        })
        .catch(error => {
            console.error('移动服务出错:', error);
            showNotification('移动服务时发生错误', 'error');
        });
}

// 批量移动服务
function batchMoveServices() {
    const sourceGroupId = batchSourceGroup.value;
    const targetGroupId = batchTargetGroup.value;

    if (sourceGroupId === targetGroupId) {
        showNotification('源分组和目标分组不能相同', 'warning');
        return;
    }

    if (!confirm('确定要将所有服务从源分组移动到目标分组吗？')) {
        return;
    }

    fetchWithAuth(API.batchMove, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                source_group_id: sourceGroupId || '',
                target_group_id: targetGroupId || ''
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification(`成功移动 ${data.moved_count} 个服务`, 'success');
                loadGroups();
                loadServices();

                // 重置选择框
                batchSourceGroup.value = '';
                batchTargetGroup.value = '';
            } else {
                showNotification('批量移动失败：' + (data.error || '未知错误'), 'error');
            }
        })
        .catch(error => {
            console.error('批量移动服务出错:', error);
            showNotification('批量移动服务时发生错误', 'error');
        });
}

// 加载分组到服务创建表单的选择框中
function loadGroupsForSelect() {
    if (!serviceGroup) return;

    fetchWithAuth(API.groups)
        .then(response => response.json())
        .then(data => {
            if (data.groups) {
                serviceGroup.innerHTML = '<option value="">默认分组</option>';

                data.groups.forEach(group => {
                    const option = document.createElement('option');
                    option.value = group.id;
                    option.textContent = group.name;
                    serviceGroup.appendChild(option);
                });
            }
        })
        .catch(error => {
            console.error('加载分组列表出错:', error);
        });
}

// 加载分组到批量操作的选择框中
function loadGroupsForBatchOperations() {
    if (!batchSourceGroup || !batchTargetGroup) return;

    fetchWithAuth(API.groups)
        .then(response => response.json())
        .then(data => {
            if (data.groups) {
                // 清空现有选项并添加默认选项
                batchSourceGroup.innerHTML = '<option value="">选择源分组...</option>';
                batchTargetGroup.innerHTML = '<option value="">选择目标分组...</option>';

                // 添加默认分组选项
                batchSourceGroup.innerHTML += '<option value="">默认分组</option>';
                batchTargetGroup.innerHTML += '<option value="">默认分组</option>';

                // 添加其他分组选项
                data.groups.forEach(group => {
                    const sourceOption = document.createElement('option');
                    sourceOption.value = group.id;
                    sourceOption.textContent = `${group.name} (${group.service_count} 个服务)`;
                    batchSourceGroup.appendChild(sourceOption);

                    const targetOption = document.createElement('option');
                    targetOption.value = group.id;
                    targetOption.textContent = `${group.name} (${group.service_count} 个服务)`;
                    batchTargetGroup.appendChild(targetOption);
                });

                // 重置预览显示
                updateBatchSourcePreview();
                updateBatchTargetPreview();
            }
        })
        .catch(error => {
            console.error('加载分组列表出错:', error);
        });
}

// 加载分组到服务详情页面的选择框中
function loadGroupsForServiceDetail(currentGroupId) {
    const groupSelect = document.getElementById('service-group-select');
    if (!groupSelect) return;

    fetchWithAuth(API.groups)
        .then(response => response.json())
        .then(data => {
            if (data.groups) {
                // 清空现有选项
                groupSelect.innerHTML = '<option value="">默认分组</option>';

                // 添加分组选项
                data.groups.forEach(group => {
                    const option = document.createElement('option');
                    option.value = group.id;
                    option.textContent = group.name;

                    // 如果是当前分组，设置为选中状态
                    if (group.id === currentGroupId) {
                        option.selected = true;
                    }

                    groupSelect.appendChild(option);
                });

                // 如果当前服务在默认分组中，选中默认分组选项
                if (!currentGroupId || currentGroupId === '') {
                    groupSelect.value = '';
                }
            }
        })
        .catch(error => {
            console.error('加载分组列表出错:', error);
        });
}

// 保存服务分组
function saveServiceGroup(serviceId, groupId) {
    fetchWithAuth(API.moveService, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                service_id: serviceId,
                group_id: groupId || ''
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const groupName = groupId ?
                    document.querySelector(`#service-group-select option[value="${groupId}"]`)?.textContent || '未知分组' :
                    '默认分组';
                showNotification(`服务已移动到: ${groupName}`, 'success');

                // 更新当前服务数据
                if (window.currentServiceData) {
                    window.currentServiceData.group_id = groupId;
                    window.currentServiceData.group_name = groupName;
                }

                // 刷新主界面的服务列表
                loadServices();
            } else {
                showNotification('更改分组失败：' + (data.error || '未知错误'), 'error');
            }
        })
        .catch(error => {
            console.error('更改服务分组出错:', error);
            showNotification('更改服务分组时发生错误', 'error');
        });
}

// 显示快速状态查看
function showQuickStatusView(service) {
    const statusInfo = `
        <div style="text-align: left;">
            <h4>服务: ${formatAddressShort(service.mapped_address || '未映射')}</h4>
            <p><strong>状态:</strong> ${service.status}</p>
            <p><strong>LAN可用性:</strong> <span class="status-badge status-${service.lan_status}">${service.lan_status || '未知'}</span></p>
            <p><strong>WAN可用性:</strong> <span class="status-badge status-${service.wan_status}">${service.wan_status || '未知'}</span></p>
            <p><strong>NAT类型:</strong> ${service.nat_type || '未知'}</p>
            <p><strong>分组:</strong> ${service.group_name || '默认分组'}</p>
            <p><strong>运行时间:</strong> ${service.start_time && service.status === '运行中' ? formatRuntime(Date.now() / 1000 - service.start_time) : '已停止'}</p>
            <p><strong>映射地址:</strong> ${service.mapped_address || '未映射'}</p>
            ${service.remark ? `<p><strong>备注:</strong> ${service.remark}</p>` : ''}
        </div>
    `;

    showNotification(statusInfo, 'info', 8000);
}

// 添加源分组选择change事件监听器
function updateBatchSourcePreview() {
    const sourceGroupId = batchSourceGroup.value;
    const previewContainer = document.getElementById('source-services-preview');

    if (!sourceGroupId) {
        previewContainer.innerHTML = '<small>请先选择源分组</small>';
        updateBatchPreview();
        return;
    }

    // 显示加载状态
    previewContainer.innerHTML = '<small>加载中...</small>';

    // 获取分组中的服务
    fetchWithAuth(`${API.groups}/services?group_id=${sourceGroupId}`)
        .then(response => response.json())
        .then(data => {
            if (data.services && data.services.length > 0) {
                let html = `<div class="services-preview-list">`;
                html += `<strong>包含 ${data.services.length} 个服务:</strong>`;

                data.services.forEach(service => {
                    const address = formatAddressShort(service.mapped_address || '未映射');
                    html += `
                        <div class="service-preview-item">
                            <span class="service-preview-address">${address}</span>
                            <span class="service-preview-status">${service.status}</span>
                        </div>
                    `;
                });
                html += '</div>';
                previewContainer.innerHTML = html;
            } else {
                previewContainer.innerHTML = '<small style="color: #999;">该分组中暂无服务</small>';
            }
            updateBatchPreview();
        })
        .catch(error => {
            console.error('获取源分组服务出错:', error);
            previewContainer.innerHTML = '<small style="color: #e74c3c;">加载失败</small>';
            updateBatchPreview();
        });
}

// 更新目标分组预览
function updateBatchTargetPreview() {
    const targetGroupId = batchTargetGroup.value;
    const infoContainer = document.getElementById('target-services-info');

    if (!targetGroupId) {
        infoContainer.innerHTML = '<small>请先选择目标分组</small>';
        updateBatchPreview();
        return;
    }

    // 获取目标分组信息
    fetchWithAuth(API.groups)
        .then(response => response.json())
        .then(data => {
            if (data.groups) {
                const targetGroup = data.groups.find(g => g.id === targetGroupId);
                if (targetGroup) {
                    infoContainer.innerHTML = `
                        <strong>${targetGroup.name}</strong><br>
                        <small>当前包含 ${targetGroup.service_count} 个服务</small>
                    `;
                } else {
                    infoContainer.innerHTML = '<small>默认分组</small>';
                }
            }
            updateBatchPreview();
        })
        .catch(error => {
            console.error('获取目标分组信息出错:', error);
            infoContainer.innerHTML = '<small style="color: #e74c3c;">加载失败</small>';
            updateBatchPreview();
        });
}

// 更新批量移动预览和按钮状态
function updateBatchPreview() {
    const sourceGroupId = batchSourceGroup.value;
    const targetGroupId = batchTargetGroup.value;
    const previewContainer = document.getElementById('batch-preview');
    const previewText = document.getElementById('preview-text');
    const moveButton = document.getElementById('batch-move-btn');

    // 检查是否选择了有效的源分组和目标分组
    // 需要特殊处理：空字符串可能是默认分组，只有当选择的文本是提示文本时才认为未选择
    const sourceSelectedText = batchSourceGroup.options[batchSourceGroup.selectedIndex]?.text || '';
    const targetSelectedText = batchTargetGroup.options[batchTargetGroup.selectedIndex]?.text || '';

    const hasValidSource = sourceSelectedText !== '选择源分组...';
    const hasValidTarget = targetSelectedText !== '选择目标分组...';
    const isDifferent = sourceGroupId !== targetGroupId || sourceSelectedText !== targetSelectedText;

    if (hasValidSource && hasValidTarget && isDifferent) {
        // 获取源分组的服务数量
        fetchWithAuth(`${API.groups}/services?group_id=${sourceGroupId}`)
            .then(response => response.json())
            .then(data => {
                const serviceCount = data.services ? data.services.length : 0;

                if (serviceCount > 0) {
                    previewText.textContent = `将要移动 ${serviceCount} 个服务`;
                    previewContainer.style.display = 'block';
                    moveButton.disabled = false;
                } else {
                    previewText.textContent = '源分组中没有服务可移动';
                    previewContainer.style.display = 'block';
                    moveButton.disabled = true;
                }
            })
            .catch(error => {
                console.error('获取服务数量出错:', error);
                previewText.textContent = '无法获取服务信息';
                previewContainer.style.display = 'block';
                moveButton.disabled = true;
            });
    } else {
        previewContainer.style.display = 'none';
        moveButton.disabled = true;

        if (hasValidSource && hasValidTarget && !isDifferent) {
            showNotification('源分组和目标分组不能相同', 'warning', 3000);
        }
    }
}

// ==================== 分组密码管理功能 ====================

// 切换密码显示/隐藏
function togglePasswordVisibility(passwordElement) {
    const password = passwordElement.dataset.password;
    const isVisible = passwordElement.classList.contains('visible');

    if (isVisible) {
        // 隐藏密码
        passwordElement.textContent = '••••••••';
        passwordElement.classList.remove('visible');
    } else {
        // 显示密码
        passwordElement.textContent = password || '未设置';
        passwordElement.classList.add('visible');
    }
}

// 临时显示密码（3秒后自动隐藏）
function showPasswordTemporarily(passwordElement) {
    const password = passwordElement.dataset.password;

    // 显示密码
    passwordElement.textContent = password || '未设置';
    passwordElement.classList.add('visible');

    // 3秒后自动隐藏
    setTimeout(() => {
        passwordElement.textContent = '••••••••';
        passwordElement.classList.remove('visible');
    }, 3000);

    showNotification('密码已显示，3秒后自动隐藏', 'info');
}

// 编辑分组密码
function editGroupPassword(groupId, groupName, currentPassword) {
    const dialog = document.getElementById('edit-group-password-dialog');
    const groupNameText = document.querySelector('#editing-group-name .group-name-text');
    const currentPasswordText = document.getElementById('current-password-text');
    const newPasswordInput = document.getElementById('new-group-password-input');

    // 设置对话框内容
    groupNameText.textContent = groupName;
    currentPasswordText.textContent = currentPassword || '未设置';
    newPasswordInput.value = '';

    // 显示对话框
    dialog.classList.add('active');

    // 存储当前编辑的分组信息
    dialog.dataset.groupId = groupId;
    dialog.dataset.groupName = groupName;

    // 聚焦到密码输入框
    setTimeout(() => {
        newPasswordInput.focus();
    }, 100);
}

// 确认修改密码
function confirmEditPassword() {
    const dialog = document.getElementById('edit-group-password-dialog');
    const groupId = dialog.dataset.groupId;
    const newPasswordInput = document.getElementById('new-group-password-input');
    const newPassword = newPasswordInput.value.trim();

    if (!newPassword) {
        showNotification('请输入新密码', 'warning');
        return;
    }

    // 发送更新请求
    fetchWithAuth(API.updateGroup, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                group_id: groupId,
                password: newPassword
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification('密码修改成功', 'success');

                // 关闭对话框
                dialog.classList.remove('active');

                // 重新加载分组列表以更新密码显示
                loadGroups();
            } else {
                showNotification('修改密码失败：' + (data.error || '未知错误'), 'error');
            }
        })
        .catch(error => {
            console.error('修改密码出错:', error);
            showNotification('修改密码时发生错误', 'error');
        });
}

// 取消修改密码
function cancelEditPassword() {
    const dialog = document.getElementById('edit-group-password-dialog');
    dialog.classList.remove('active');
}