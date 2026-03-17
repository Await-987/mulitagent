# AIOS Workforce 实时可视化仪表板

## 功能特性

- **实时任务展示** - WebSocket实时推送任务更新
- **状态颜色区分** - 任务状态可视化
  - 灰色：已创建 (created)
  - 蓝色：已分配 (assigned)
  - 黄色：进行中 (started)
  - 绿色：已完成 (completed)
- **依赖关系可视化** - 虚线箭头显示任务间的依赖关系
- **Agent信息展示** - 显示执行Agent
- **执行结果** - 实时显示任务执行结果

## 在aios_demo.py中，需要添加的代码
- 添加的部分 part.1 , 在test_monitor.py的 " 28-139 " 行
- 添加的部分 part.2 , 在test_monitor.py的 " 211-212 " 行

## 安装依赖 (在原有虚拟环境的基础上，添加flask所需的依赖)
```bash
cd demo
pip install -r requirements.txt
```
```bash
 ┌───────────────────────────┐
 │   dashboard need:         │
 │  Flask==2.3.3             │
 │  flask-socketio==5.3.4    │
 │  python-socketio==5.9.0   │
 │  python-engineio==4.7.1   │
 └───────────────────────────┘
```

## 快速开始
### 在第 1 个终端
```bash
cd demo
python event_api.py
```
### 在第 2 个终端:
```bash
python -m demo.test_monitor.py
```
### 打开 浏览器 访问：
```
http://127.0.0.1:5000
```

## 项目结构
```
├── demo/
│   ├── __init__.py
|   |
│   ├── monitor/
│   │   ├── __init__.py
│   │   ├── static\ 
│   │   |   ├── logo.png 
│   │   ├── templates\
│   │   |   ├── dashboard.html
│   │   ├── event_api.py 
│   │   ├── requirements.txt 
│   │   ├── run_dashboard.sh
│   │   └── run_event_artifacts.py
|   |
│   └── dashboard_test.py
```



## 工作原理

1. **事件收集** - `test_workforce_events.py`执行任务时，将事件写入`working_dir/[时间戳]/`目录下的`.txt`文件

2. **事件监控** - `event_api.py`的后台线程持续扫描新事件文件

3. **事件解析** - 解析`.txt`文件内容，提取任务信息（ID、状态、依赖关系等）

4. **实时推送** - 通过WebSocket将事件实时推送到前端

5. **界面更新** - 前端接收事件后，动画展示任务的分解和执行过程

## 事件类型

### task_created
主任务创建事件

```
timestamp: 2026-02-27T06:11:21.062912+00:00
workforce_id: 2201323553456
event_type: task_created
task_id: 0
description: 我最近去了云南旅游了，你帮我看看我相册、备忘录里面的一些东西，整理一下去小红书发个帖子
```

### task_decomposed
任务分解事件 - 主任务分解为若干子任务

```
timestamp: 2026-02-27T06:11:53.312517+00:00
workforce_id: 2201323553456
event_type: task_decomposed
parent_task_id: 0
subtask_ids: ['0.1', '0.2', '0.3', '0.4']
```

### task_assigned
子任务分配事件 - 分配给特定Agent

```
timestamp: 2026-02-27T06:12:11.983026+00:00
event_type: task_assigned
task_id: 0.1
worker_id: 1c0fa642-b278-4f11-8bd5-0155755905c1
worker_role: Photos Agent: ...
dependencies: []
```

### task_started
任务开始执行

```
event_type: task_started
task_id: 0.1
timestamp: ...
```

### task_completed
任务完成执行

```
event_type: task_completed
task_id: 0.1
result: {}
timestamp: ...
```

## API接口

### GET /
返回仪表板HTML页面

### GET /api/tasks
获取所有任务信息

**返回示例：**
```json
{
  "0": {
    "id": "0",
    "description": "主任务描述",
    "status": "decomposed",
    "subtasks": ["0.1", "0.2"],
    "timestamp": "2026-02-27T06:11:21.062912+00:00"
  },
  "0.1": {
    "id": "0.1",
    "status": "completed",
    "worker_id": "...",
    "dependencies": [],
    "result": "执行结果"
  }
}
```

### GET /api/events
获取所有原始事件

## WebSocket事件

客户端连接时接收：

- `initial_data` - 初始化数据（所有已有任务）
- `task_created` - 新任务创建
- `task_decomposed` - 任务分解完成
- `task_assigned` - 任务分配完成
- `task_started` - 任务开始执行
- `task_completed` - 任务执行完成

## 故障排除

### 端口已被占用

如果5000端口已被占用，编辑`event_api.py`最后一行：

```python
socketio.run(app, host='127.0.0.1', port=5001, debug=False)  # 改为其他端口
```

### 无法连接WebSocket

确保：
1. API服务正确启动（无错误日志）
2. 防火墙未阻止5000端口
3. 浏览器支持WebSocket

### 任务事件未显示

检查：
1. `working_dir/`目录是否存在
2. 事件文件是否被正确生成（`.txt`文件）
3. API日志中是否有parsing错误

## 自定义配置

### 修改工作目录

在`event_api.py`中修改：
```python
WORKING_DIRECTORY = "/your/custom/path"
```

### 修改端口

在`event_api.py`中修改：
```python
socketio.run(app, host='127.0.0.1', port=8080, debug=False)
```

### 修改样式

编辑`templates/dashboard.html`中的`<style>`部分

