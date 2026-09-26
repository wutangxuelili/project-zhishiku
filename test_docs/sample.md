# asyncio 异步IO知识库文档
> 文件名称：asyncio.md
> 用途：Python asyncio 异步编程知识库，适合内部文档、笔记、面试复习

## 1. asyncio 简介
`asyncio` 是 Python 3.4+ 引入的**标准库异步IO框架**，用于编写**并发（concurrent）**代码，基于**事件循环（Event Loop）**实现协程调度。

> 核心特点：
> - 单线程内实现多任务并发，不是多并行（并行需要多CPU核心，多进程）
> - IO等待时让出CPU，切换执行其他任务，提升IO密集型场景效率
> - 适合网络请求、数据库读写、文件IO等大量等待的场景；**不适合CPU密集型任务**

关键词区分：
- **同步**：一个任务执行完，再执行下一个，IO阻塞时线程卡住等待
- **异步**：遇到IO阻塞时，暂停当前协程，去执行其他就绪任务，IO完成后再回来继续执行
- **并发 Concurrent**：同一时间段多个任务交替执行（asyncio 属于并发）
- **并行 Parallel**：同一时刻多个任务同时运行（多进程）

## 2. 基础概念
### 2.1 协程 Coroutine
协程是可暂停、可恢复的函数，使用 `async def` 定义。
- `async def func()`：定义协程函数，调用后**不会直接执行**，只会返回协程对象
- `await`：在协程内部使用，用来等待可等待对象完成，并交出事件循环控制权

> 可等待对象（Awaitable）三类：
> 1. 协程对象 Coroutine
> 2. 任务 Task
> 3. Future

### 2.2 事件循环 EventLoop
事件循环是 asyncio 的核心调度器：
- 负责注册、调度、执行协程/任务
- 监听IO事件，当await的IO就绪时，恢复对应协程执行
- Python3.7+ 推荐使用高层API：`asyncio.run()`，自动创建、关闭事件循环，不再需要手动管理loop

### 2.3 Task 任务
`asyncio.create_task()` 将协程包装成Task，提交给事件循环**后台并发执行**。
> Task 是协程的容器，用于并发调度多个协程。

### 2.4 Future
Future 代表一个**尚未完成操作的结果占位符**，底层对象，一般业务代码很少直接使用。Task继承自Future。

## 3. 基础语法示例
### 3.1 最简单协程
```python
import asyncio

# 定义协程函数
async def hello():
    print("hello start")
    # 模拟IO等待，await让出控制权
    await asyncio.sleep(1)
    print("hello end")

# 入口，Python3.7+
asyncio.run(hello())
