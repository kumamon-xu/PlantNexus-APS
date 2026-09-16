# PlantNexus APS

通用产品后续建设见[演进路线](docs/core/sme-generalization-roadmap.md)与[仿真验证及后期校准策略](docs/simulation/generalized-product-validation-and-calibration.md)。当前通过模拟/仿真推进研发，保留后期真实项目接入方法；路线中的新增能力尚未实现。

PlantNexus APS 是一个面向离散制造的高级计划与排程系统。项目采用 Simulation-first 路线，把canonical数据、不可变计划快照、PlanningProblem、OR-Tools CP-SAT 求解、独立排程校验、计划版本审批/发布、内部导出和动态重排串成一条可重放链路。

APS 接收宿主平台提交的 versioned canonical JSON，负责数据验证、不可变计划输入、异步求解、独立校验、版本管理与受权输出。ERP/MES/WMS/CAM 的采集、字段映射和结果展示由宿主负责；可选 React 工作台使用同一 Headless API。

企业通过独立 Enterprise Extension 项目和指定版本的 SDK 扩展业务规则。Extension 由 Runtime 在服务端受控加载，不复制 APS Core。组件分别版本化，升级需要显式选择和兼容验证。

本项目提供 TEST/SIMULATION 工程运行能力。真实业务校准、企业规则验收、容量与 Production 上线需在目标环境单独完成。

## 已有能力

- 标准导入、字段归一化、数据质量校验和不可变 PlanningSnapshot；
- PlanningProblem v2、全局 CP-SAT 排程、参考调度器和独立 ScheduleValidator；
- 计划运行、ScheduleVersion、审批/驳回、内部发布、ExportJob 与可验证导出包；
- ExecutionEvent、事实投影、冻结窗口、稳定性目标、ChangeReport 和动态重排；
- React + TypeScript 双语计划工作台、甘特图、资源负荷、版本比较和重排视图；
- Extension SDK六类稳定SPI、受控Runtime Registry/loader和不含Core副本的Enterprise Extension模板与conformance工具；
- Runtime、Extension SDK 与 Developer Kit 分发，配套精确版本锁、兼容检查和升级/回滚工具；
- 仅限 Simulation/TEST、默认关闭并可精确回退标准工时的工时预测链路。

能力边界和未支持项以[能力矩阵](docs/core/capability-matrix.md)为准。FEASIBLE 只表示找到可行解，UNKNOWN 不等于无解；任何候选排程必须经独立 Validator 通过后才能进入可评审版本。

## 技术基线

| 范围 | 当前基线 |
|---|---|
| Backend | Python 3.12、FastAPI、SQLAlchemy、Alembic、Celery |
| Solver | OR-Tools CP-SAT 9.15.6755 |
| Storage / queue | PostgreSQL 17、Redis 8 |
| Frontend | React 19、TypeScript 6、Ant Design 6、TanStack Query、Vite |
| Test | pytest、Hypothesis、Vitest、Testing Library、Playwright |
| Release / contract versions | Runtime 0.1.0、Extension SDK 1.0.0、Application/Core 0.0.0、Headless API v1、Schema set 2.10.0、database 0009 |

## 下载与部署

发行包通过 [GitHub Releases](https://github.com/kumamon-xu/PlantNexus-APS/releases) 提供：

| 发布资产 | 用途 |
|---|---|
| 离线部署包 | Linux/amd64 Docker 镜像、Compose、配置模板、安装与恢复脚本 |
| Runtime 包 | Python Runtime、依赖锁、安装清单和供应链元数据 |
| Developer Kit | 精确绑定的 Runtime、SDK、扩展模板、示例和 conformance 工具 |
| 公共接口与文档包 | API、Schema、SDK 接口参考与项目技术文档 |

GitHub tag 表示整组发行，Runtime、SDK、Kit 等内部版本独立管理。以每次发行的资产清单、嵌套版本锁和 SHA-256 为准；相同 Runtime 版本号不代表相同归档内容。

离线部署不需要源码、宿主 Python 或联网构建。先核对摘要并准备显式 TEST/SIMULATION 配置，再按[安装与配置清单](docs/operations/deployment.md#最终企业离线交接)执行。企业扩展代码、密钥和业务配置由部署方提供。

## 快速开始

### 1. Backend 依赖与 API 外壳

需要 Python 3.12 和 [uv](https://docs.astral.sh/uv/)。

```powershell
uv sync --locked
uv run uvicorn app.api.app:app --host 127.0.0.1 --port 8000
```

可访问：

- `GET http://127.0.0.1:8000/health/live`
- `GET http://127.0.0.1:8000/health/ready`
- `GET http://127.0.0.1:8000/openapi.json`

Swagger UI 和 ReDoc 默认关闭。默认组合根没有注入业务 application port 与身份授权 provider，因此 `/api/v1/**` 业务请求会安全拒绝；完整接口状态和待接入项见 [API 接口开发清单](docs/contracts/api-development-checklist.md)。

完整业务运行应使用 Runtime 分发中的组合根、持久化存储、Worker 与显式身份授权配置。Worker 使用 lease/heartbeat 和不可变 checkpoint 处理重复、崩溃、取消与超时；候选必须经过独立 Validator 和已配置的 Extension Validation Rule 才能成为可评审版本。CSV/XLSX 参考适配器不是公共 Headless 输入接口。

### Runtime工程distribution

生成并完整验证内容寻址发布物：

```powershell
uv run python -m app.infrastructure.release.check `
  --root . `
  --release-output build/release `
  --report build/validation/runtime-release.json `
  --compatibility-report build/validation/runtime-release-compatibility.json `
  --migration-report build/validation/runtime-release-migration.json `
  --security-report build/validation/runtime-release-security.json `
  --benchmark-report build/benchmarks/runtime-release.json
```

发布身份、内容、安装、preflight与rollback规则见[发布与版本合同](docs/operations/release-and-versioning.md)及[安装与启动顺序](docs/operations/deployment.md)。输出位于已忽略的`build/`，不得提交或视为Production promotion。

### Extension与Developer Kit

企业扩展必须在独立项目中使用指定版本的Extension SDK开发，通过Developer Kit内的模板、测试工具和conformance入口验证，再由匹配的Runtime在build/deploy/startup阶段受控装载。Extension不得进入宿主或浏览器运行，不得复制Core、直写APS数据库或创建私有业务API。版本与升级规则见[Extension SDK、Runtime 与 Developer Kit 架构](docs/architecture/extension-sdk-runtime-and-developer-kit.md)和[Developer Kit发布、升级与回滚](docs/operations/developer-kit-release-upgrade-and-rollback.md)。

### 2. 本地依赖服务

复制示例配置并替换所有 `replace-me` 值，再启动开发用 PostgreSQL、Redis、API 和 worker：

```powershell
Copy-Item .env.example .env
docker compose --env-file .env up --build
```

该 Compose 文件只用于本地开发，不包含生产密钥、外部身份系统、生产数据源或前端托管。

### 3. Frontend 开发与构建

需要 Node.js 24.19.0 与 npm 11.17.0。

```powershell
npm --prefix frontend ci
npm --prefix frontend run dev
npm --prefix frontend run build
```

Frontend 默认使用同源 `/api/v1`，并对非隔离的 Simulation 配置 fail closed。联调时需要显式的同源反向代理或合规的 HTTPS API 地址，以及可用的后端 application/authorization 适配器；E2E 测试使用独立的测试隔离配置。

## 本地验收

常用完整检查：

```powershell
uv run ruff check .
uv run pyright backend/app backend/tests
uv run pytest -q
uv run python scripts/check_docs.py
uv build

npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run test -- --run
npm --prefix frontend run build
```

动态场景和基准测试有独立命令；按受影响模块选择对应合同文档和测试。

## 文档入口

- [公开文档中心](docs/README.md)
- [API 接口开发清单](docs/contracts/api-development-checklist.md)
- [数据字段中文名称字典](docs/contracts/data-field-dictionary.md)
- [Schema 索引](docs/contracts/schema-index.md)
- [端到端计划流程](docs/architecture/end-to-end-planning-flow.md)
- [Headless 产品化与平台集成](docs/architecture/headless-productization-and-platform-integration.md)
- [Extension SDK、Runtime 与 Developer Kit 架构](docs/architecture/extension-sdk-runtime-and-developer-kit.md)
- [Runtime 发布、版本与回退合同](docs/operations/release-and-versioning.md)
- [Runtime 安装、预检与启动顺序](docs/operations/deployment.md)
- [领域模型](docs/domain/domain-model.md)
- [约束目录](docs/planning/constraint-catalog.md)
- [独立排程校验器](docs/planning/schedule-validator.md)
- [Frontend 文档](docs/frontend/README.md)
- [安全边界](docs/operations/security.md)

## 仓库结构

```text
backend/      Python 领域、应用、API、基础设施、求解器和测试
frontend/     React/TypeScript 工作台、单元测试和浏览器测试
schemas/      JSON Schema、规则注册表、样例与机器数据字典
fixtures/     版本化合成场景、非法样例和黄金数据
benchmarks/   可重放基准 profile 与 baseline
docs/         仅公开、核心、可维护的项目与技术文档
scripts/      文档治理、CI、证据与基准命令
infra/        本地容器构建配置
```

开发报告、测试输出、coverage、浏览器制品和临时草稿必须留在已忽略的 `build/`、缓存或工具输出目录，不能提交到 `docs/`。新增公开文档应放入现有文档分区，并同时维护[文档中心](docs/README.md)中的入口。
