# PlantNexus APS

PlantNexus APS 是一个面向离散制造的高级计划与排程系统。项目采用 Simulation-first 路线，把标准数据导入、不可变计划快照、PlanningProblem、OR-Tools CP-SAT 求解、独立排程校验、计划版本审批/发布、内部导出和动态重排串成一条可重放链路。

当前仓库是“已实现的研发基线”，不是生产部署包：P0～P6 能力已经形成，P7 真实数据校准因缺少获授权的真实数据、真实环境和业务责任人而暂缓。默认 FastAPI 组合根会对未注入的业务应用与授权适配器 fail closed；健康检查和 OpenAPI 可用，但不能把默认启动等同于开箱即用的生产 APS。

## 已有能力

- 标准导入、字段归一化、数据质量校验和不可变 PlanningSnapshot；
- PlanningProblem v2、全局 CP-SAT 排程、参考调度器和独立 ScheduleValidator；
- 计划运行、ScheduleVersion、审批/驳回、内部发布、ExportJob 与可验证导出包；
- ExecutionEvent、事实投影、冻结窗口、稳定性目标、ChangeReport 和动态重排；
- React + TypeScript 双语计划工作台、甘特图、资源负荷、版本比较和重排视图；
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
| Contract versions | Spec 0.3.0、Schema set 2.9.0、code 0.0.0（研发占位版本） |

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

动态场景、基准测试和阶段 Gate 有独立命令；按受影响模块选择对应合同文档和测试，不把历史运行编号复制到 README。

## 文档入口

- [公开文档中心](docs/README.md)
- [API 接口开发清单](docs/contracts/api-development-checklist.md)
- [数据字段中文名称字典](docs/contracts/data-field-dictionary.md)
- [Schema 索引](docs/contracts/schema-index.md)
- [端到端计划流程](docs/architecture/end-to-end-planning-flow.md)
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
