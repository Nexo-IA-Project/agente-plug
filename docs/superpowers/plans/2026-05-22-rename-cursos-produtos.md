# Rename Cursos → Produtos — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the "Courses" concept to "Products" everywhere — database table, API endpoints, domain entities, repositories, and frontend components/routes.

**Architecture:** Pure rename — no behavior changes. Migration renames `courses` → `products` and the `course_id` FK in `followup_flows` → `product_id`. All Python and TypeScript symbols follow the rename. The `/courses` Next.js route gets a 301 redirect to `/products`.

**Tech Stack:** SQLAlchemy/Alembic (migration), FastAPI (router rename), Python dataclasses (entities), TypeScript/Next.js App Router (frontend)

---

## File Map

**Backend — create/rename:**
- `migrations/versions/<hash>_rename_courses_to_products.py` — new migration
- `src/shared/domain/entities/product.py` — was `course.py` (rename class + file)
- `src/shared/domain/ports/product_repository.py` — was `course_repository.py`
- `src/shared/adapters/db/repositories/product_repo.py` — was `course_repo.py`
- `src/interface/http/routers/admin/products.py` — was `courses.py`

**Backend — modify:**
- `src/shared/adapters/db/models.py` — `CourseModel` tablename + FK
- `src/shared/domain/entities/followup.py` — `course_id` → `product_id`
- `src/interface/http/schemas/followup.py` — `course_id` → `product_id`
- `src/shared/adapters/db/repositories/followup_flow_repo.py` — imports + field refs
- `src/shared/adapters/db/repositories/followup_enrollment_repo.py` — `CourseModel` import
- `src/shared/application/purchase_handler.py` — `_course_repo` → `_product_repo`
- `src/interface/worker/handlers/purchase.py` — `course_repo` → `product_repo`
- `src/interface/http/routers/admin/followup.py` — imports + field refs
- `src/main.py` — router import + registration

**Frontend — create:**
- `src/app/(admin)/products/page.tsx` — was `courses/page.tsx`

**Frontend — modify:**
- `src/features/courses/types.ts` — `Course` → `Product`
- `src/features/courses/hooks/useCourses.ts` — exports rename
- `src/features/courses/components/CourseCard.tsx` — prop type rename
- `src/features/courses/components/CourseDrawer.tsx` — prop type rename
- `src/app/(admin)/courses/page.tsx` — add redirect to `/products`
- `src/lib/api.ts` — function names + endpoint paths
- `src/features/followup/types.ts` — `CourseSummary` → `ProductSummary`, `course_id` → `product_id`
- `src/features/followup/components/FlowDrawer.tsx` — link href

---

### Task 1: Migration — Rename tabela + FK

**Files:**
- Create: `apps/api/migrations/versions/<hash>_rename_courses_to_products.py`

- [ ] **Step 1: Criar arquivo de migration**

```bash
cd apps/api
uv run alembic revision --autogenerate -m "rename_courses_to_products"
```

Abrir o arquivo gerado e substituir o conteúdo por:

```python
"""rename courses to products

Revision ID: <gerado_automaticamente>
Revises: <revision_anterior>
Create Date: 2026-05-22

"""
from __future__ import annotations

from alembic import op

revision = "<gerado_automaticamente>"
down_revision = "<revision_anterior>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Renomeia constraint única antes de renomear tabela
    op.execute("ALTER TABLE courses RENAME CONSTRAINT uq_courses_account_hubla TO uq_products_account_hubla")
    op.execute("ALTER INDEX ix_courses_account_id RENAME TO ix_products_account_id")

    # Renomeia a tabela
    op.rename_table("courses", "products")

    # Renomeia a coluna FK em followup_flows
    op.execute("ALTER TABLE followup_flows RENAME COLUMN course_id TO product_id")

    # Renomeia a FK constraint
    op.execute("""
        ALTER TABLE followup_flows
        DROP CONSTRAINT IF EXISTS followup_flows_course_id_fkey
    """)
    op.execute("""
        ALTER TABLE followup_flows
        ADD CONSTRAINT followup_flows_product_id_fkey
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE followup_flows
        DROP CONSTRAINT IF EXISTS followup_flows_product_id_fkey
    """)
    op.execute("""
        ALTER TABLE followup_flows
        ADD CONSTRAINT followup_flows_course_id_fkey
        FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE RESTRICT
    """)
    op.execute("ALTER TABLE followup_flows RENAME COLUMN product_id TO course_id")
    op.rename_table("products", "courses")
    op.execute("ALTER TABLE products RENAME CONSTRAINT uq_products_account_hubla TO uq_courses_account_hubla")
    op.execute("ALTER INDEX ix_products_account_id RENAME TO ix_courses_account_id")
```

> **Nota:** Substituir `<gerado_automaticamente>` e `<revision_anterior>` pelos valores reais do arquivo gerado pelo alembic.

- [ ] **Step 2: Rodar migration e verificar**

```bash
cd apps/api
uv run alembic upgrade heads
```

Esperado: `Running upgrade ... -> <rev>, rename courses to products`

Verificar no banco:
```bash
uv run python -c "
import asyncio
from shared.adapters.db.session import get_sessionmaker
from sqlalchemy import text

async def check():
    async with get_sessionmaker()() as s:
        r = await s.execute(text(\"SELECT table_name FROM information_schema.tables WHERE table_name IN ('products','courses') AND table_schema='public'\"))
        print(r.fetchall())

asyncio.run(check())
"
```

Esperado: `[('products',)]` — só `products`, sem `courses`.

- [ ] **Step 3: Commit**

```bash
git add apps/api/migrations/versions/
git commit -m "feat(db): renomeia tabela courses → products, FK course_id → product_id"
```

---

### Task 2: Backend — Domain + Repository

**Files:**
- Create: `apps/api/src/shared/domain/entities/product.py`
- Create: `apps/api/src/shared/domain/ports/product_repository.py`
- Create: `apps/api/src/shared/adapters/db/repositories/product_repo.py`
- Modify: `apps/api/src/shared/adapters/db/models.py`
- Modify: `apps/api/src/shared/domain/entities/followup.py`

- [ ] **Step 1: Criar entidade Product**

`apps/api/src/shared/domain/entities/product.py`:
```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(slots=True)
class Product:
    id: UUID
    account_id: UUID
    name: str
    hubla_id: str
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None
```

- [ ] **Step 2: Criar port ProductRepository**

`apps/api/src/shared/domain/ports/product_repository.py`:
```python
from __future__ import annotations

from typing import Protocol
from uuid import UUID

from shared.domain.entities.product import Product


class ProductRepository(Protocol):
    async def list_by_account(self, account_id: UUID) -> list[Product]: ...
    async def find_by_id(self, product_id: UUID) -> Product | None: ...
    async def find_active_by_hubla_id(self, account_id: UUID, hubla_id: str) -> Product | None: ...
    async def create(
        self, *, account_id: UUID, name: str, hubla_id: str, is_active: bool = True
    ) -> Product: ...
    async def update(
        self,
        product_id: UUID,
        *,
        name: str | None = None,
        hubla_id: str | None = None,
        is_active: bool | None = None,
    ) -> Product | None: ...
    async def delete(self, product_id: UUID) -> bool: ...
    async def count_flows(self, product_id: UUID) -> int: ...
```

- [ ] **Step 3: Criar repositório SqlProductRepository**

`apps/api/src/shared/adapters/db/repositories/product_repo.py`:
```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import ProductModel, FollowupFlowModel
from shared.domain.entities.product import Product


def _to_entity(m: ProductModel) -> Product:
    return Product(
        id=m.id,
        account_id=m.account_id,
        name=m.name,
        hubla_id=m.hubla_id,
        is_active=m.is_active,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


@dataclass
class SqlProductRepository:
    session: AsyncSession

    async def list_by_account(self, account_id: UUID) -> list[Product]:
        stmt = (
            select(ProductModel)
            .where(ProductModel.account_id == account_id)
            .order_by(ProductModel.name)
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return [_to_entity(m) for m in rows]

    async def find_by_id(self, product_id: UUID) -> Product | None:
        m = await self.session.get(ProductModel, product_id)
        return _to_entity(m) if m else None

    async def find_active_by_hubla_id(self, account_id: UUID, hubla_id: str) -> Product | None:
        stmt = select(ProductModel).where(
            ProductModel.account_id == account_id,
            ProductModel.hubla_id == hubla_id,
            ProductModel.is_active.is_(True),
        )
        m = (await self.session.execute(stmt)).scalar_one_or_none()
        return _to_entity(m) if m else None

    async def create(
        self, *, account_id: UUID, name: str, hubla_id: str, is_active: bool = True
    ) -> Product:
        now = datetime.now(UTC)
        m = ProductModel(
            id=uuid4(),
            account_id=account_id,
            name=name,
            hubla_id=hubla_id,
            is_active=is_active,
            created_at=now,
            updated_at=now,
        )
        self.session.add(m)
        await self.session.flush()
        return _to_entity(m)

    async def update(
        self,
        product_id: UUID,
        *,
        name: str | None = None,
        hubla_id: str | None = None,
        is_active: bool | None = None,
    ) -> Product | None:
        m = await self.session.get(ProductModel, product_id)
        if m is None:
            return None
        if name is not None:
            m.name = name
        if hubla_id is not None:
            m.hubla_id = hubla_id
        if is_active is not None:
            m.is_active = is_active
        m.updated_at = datetime.now(UTC)
        await self.session.flush()
        return _to_entity(m)

    async def delete(self, product_id: UUID) -> bool:
        m = await self.session.get(ProductModel, product_id)
        if m is None:
            return False
        await self.session.delete(m)
        await self.session.flush()
        return True

    async def count_flows(self, product_id: UUID) -> int:
        stmt = select(func.count(FollowupFlowModel.id)).where(
            FollowupFlowModel.product_id == product_id
        )
        return int((await self.session.execute(stmt)).scalar_one())
```

- [ ] **Step 4: Atualizar models.py — renomear CourseModel**

Em `apps/api/src/shared/adapters/db/models.py`:

Localizar `class CourseModel(Base):` e renomear para `ProductModel`. Atualizar `__tablename__` de `"courses"` para `"products"`. Atualizar constraints:
```python
class ProductModel(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("account_id", "hubla_id", name="uq_products_account_hubla"),
        Index("ix_products_account_id", "account_id"),
    )
    # ... campos iguais
```

Localizar a FK em `FollowupFlowModel` que aponta para `courses.id` e renomear campo e referência:
```python
# Antes:
course_id: Mapped[uuid.UUID] = mapped_column(
    ForeignKey("courses.id", ondelete="RESTRICT"),
)

# Depois:
product_id: Mapped[uuid.UUID] = mapped_column(
    ForeignKey("products.id", ondelete="RESTRICT"),
)
```

- [ ] **Step 5: Atualizar entidade FollowupFlow**

Em `apps/api/src/shared/domain/entities/followup.py`, linha 26:
```python
# Antes:
course_id: UUID

# Depois:
product_id: UUID
```

- [ ] **Step 6: Rodar testes unitários**

```bash
cd apps/api
uv run pytest tests/unit -v -x
```

Esperado: todos passando (ou falhas esperadas referentes a `course_id` que serão corrigidas nas próximas tasks).

- [ ] **Step 7: Commit**

```bash
git add apps/api/src/shared/domain/entities/product.py \
        apps/api/src/shared/domain/ports/product_repository.py \
        apps/api/src/shared/adapters/db/repositories/product_repo.py \
        apps/api/src/shared/adapters/db/models.py \
        apps/api/src/shared/domain/entities/followup.py
git commit -m "feat(api): renomeia CourseModel → ProductModel, Course → Product, course_id → product_id"
```

---

### Task 3: Backend — Schemas + Routers

**Files:**
- Modify: `apps/api/src/interface/http/schemas/followup.py`
- Create: `apps/api/src/interface/http/routers/admin/products.py`
- Modify: `apps/api/src/interface/http/routers/admin/followup.py`
- Modify: `apps/api/src/shared/adapters/db/repositories/followup_flow_repo.py`
- Modify: `apps/api/src/shared/adapters/db/repositories/followup_enrollment_repo.py`
- Modify: `apps/api/src/shared/application/purchase_handler.py`
- Modify: `apps/api/src/interface/worker/handlers/purchase.py`
- Modify: `apps/api/src/main.py`

- [ ] **Step 1: Atualizar schemas followup — course_id → product_id**

Em `apps/api/src/interface/http/schemas/followup.py`:

```python
# Substituir em CreateFlowRequest:
product_id: UUID  # era course_id

# Substituir em UpdateFlowRequest:
product_id: UUID | None = None  # era course_id

# Substituir em FollowupFlowResponse (se existir course_id):
product_id: UUID  # era course_id
```

- [ ] **Step 2: Criar router admin/products.py**

`apps/api/src/interface/http/routers/admin/products.py` — copiar conteúdo de `courses.py` e fazer substituições:

```python
# Renomear todos os símbolos:
# SqlCourseRepository → SqlProductRepository
# course_repo.py → product_repo.py
# CourseResponse → ProductResponse
# CreateCourseRequest → CreateProductRequest
# UpdateCourseRequest → UpdateProductRequest
# "/courses" → "/products"
# "course_id" → "product_id"
# "course not found" → "product not found"
# "course has" → "product has"
# "course with hubla_id" → "product with hubla_id"
```

Resultado:
```python
from __future__ import annotations

import uuid as _uuid_module
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from interface.http.deps.admin_auth import AdminAuth, require_admin
from shared.adapters.db.models import AccountModel
from shared.adapters.db.repositories.product_repo import SqlProductRepository
from shared.adapters.db.session import session_scope

router = APIRouter(tags=["admin-products"])


class CreateProductRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    hubla_id: str = Field(min_length=1, max_length=200)
    is_active: bool = True


class UpdateProductRequest(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    hubla_id: str | None = Field(default=None, max_length=200)
    is_active: bool | None = None


class ProductResponse(BaseModel):
    id: UUID
    name: str
    hubla_id: str
    is_active: bool
    flow_count: int
    created_at: datetime
    updated_at: datetime


async def _get_account_uuid(session: object) -> _uuid_module.UUID:
    result = await session.execute(select(AccountModel.id).limit(1))  # type: ignore[attr-defined]
    value: _uuid_module.UUID = result.scalar_one()
    return value


@router.get("/products", response_model=list[ProductResponse])
async def list_products(
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> list[ProductResponse]:
    async with session_scope() as session:
        account_uuid = await _get_account_uuid(session)
        repo = SqlProductRepository(session=session)
        products = await repo.list_by_account(account_uuid)
        items: list[ProductResponse] = []
        for p in products:
            items.append(
                ProductResponse(
                    id=p.id,
                    name=p.name,
                    hubla_id=p.hubla_id,
                    is_active=p.is_active,
                    flow_count=await repo.count_flows(p.id),
                    created_at=p.created_at,
                    updated_at=p.updated_at,
                )
            )
    return items


@router.post("/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    body: CreateProductRequest,
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> ProductResponse:
    async with session_scope() as session:
        account_uuid = await _get_account_uuid(session)
        repo = SqlProductRepository(session=session)
        try:
            p = await repo.create(
                account_id=account_uuid,
                name=body.name,
                hubla_id=body.hubla_id,
                is_active=body.is_active,
            )
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="product with hubla_id already exists",
            ) from exc
    return ProductResponse(
        id=p.id, name=p.name, hubla_id=p.hubla_id, is_active=p.is_active,
        flow_count=0, created_at=p.created_at, updated_at=p.updated_at,
    )


@router.put("/products/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: UUID,
    body: UpdateProductRequest,
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> ProductResponse:
    async with session_scope() as session:
        repo = SqlProductRepository(session=session)
        try:
            p = await repo.update(
                product_id,
                name=body.name,
                hubla_id=body.hubla_id,
                is_active=body.is_active,
            )
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="product with hubla_id already exists",
            ) from exc
        if p is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="product not found")
        flow_count = await repo.count_flows(p.id)
    return ProductResponse(
        id=p.id, name=p.name, hubla_id=p.hubla_id, is_active=p.is_active,
        flow_count=flow_count, created_at=p.created_at, updated_at=p.updated_at,
    )


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: UUID,
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> None:
    async with session_scope() as session:
        repo = SqlProductRepository(session=session)
        existing = await repo.find_by_id(product_id)
        if existing is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="product not found")
        flow_count = await repo.count_flows(product_id)
        if flow_count > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"product has {flow_count} flow(s) linked",
            )
        await repo.delete(product_id)
```

- [ ] **Step 3: Atualizar followup_flow_repo.py**

Em `apps/api/src/shared/adapters/db/repositories/followup_flow_repo.py`:

Atualizar referências de `course_id` → `product_id`:
```python
# _to_entity: course_id=m.course_id → product_id=m.product_id
# list_active_by_course: renomear para list_active_by_product, atualizar filtro
# create: course_id=course_id → product_id=product_id (parâmetro)
# update: course_id → product_id
```

Renomear método:
```python
async def list_active_by_product(self, product_id: uuid.UUID) -> list[FollowupFlow]:
    stmt = select(FollowupFlowModel).where(
        FollowupFlowModel.product_id == product_id,
        FollowupFlowModel.is_active.is_(True),
    )
    ...
```

- [ ] **Step 4: Atualizar followup_enrollment_repo.py**

Substituir `CourseModel` por `ProductModel` e `course_name` label por `product_name`:
```python
from shared.adapters.db.models import ProductModel, ...

# No join:
.outerjoin(ProductModel, ProductModel.id == FollowupFlowModel.product_id)
# No label:
ProductModel.name.label("product_name"),
```

- [ ] **Step 5: Atualizar purchase_handler.py**

```python
# __init__: course_repo → product_repo, self._course_repo → self._product_repo
# handle_one: 
#   self._course_repo.find_active_by_hubla_id → self._product_repo.find_active_by_hubla_id
#   log.warning: course_not_found → product_not_found
#   self._flow_repo.list_active_by_course → self._flow_repo.list_active_by_product
#   log.info: course_id= → product_id=
```

- [ ] **Step 6: Atualizar worker/handlers/purchase.py**

```python
# Substituir:
from shared.adapters.db.repositories.product_repo import SqlProductRepository
# ...
product_repo = SqlProductRepository(session=session)
# ...
course_repo=product_repo → product_repo=product_repo
```

- [ ] **Step 7: Atualizar followup.py router — course_id → product_id**

Em `apps/api/src/interface/http/routers/admin/followup.py`:

```python
# Import:
from shared.adapters.db.repositories.product_repo import SqlProductRepository
# ...
# Todas as variáveis course_repo → product_repo
# body.course_id → body.product_id
# flow.course_id → flow.product_id
# course = await product_repo.find_by_id(...)
```

- [ ] **Step 8: Atualizar main.py**

Em `apps/api/src/main.py`:
```python
# Antes:
from interface.http.routers.admin import courses as admin_courses
# ...
app.include_router(admin_courses.router, prefix="/admin")

# Depois:
from interface.http.routers.admin import products as admin_products
# ...
app.include_router(admin_products.router, prefix="/admin")
```

Opcionalmente manter o router de `courses` com um deprecation note se necessário.

- [ ] **Step 9: Rodar todos os testes unitários**

```bash
cd apps/api
uv run pytest tests/unit -v -x
```

Esperado: todos passando.

- [ ] **Step 10: Rodar lint e type check**

```bash
cd apps/api
uv run ruff check src tests
uv run mypy src
```

Esperado: sem erros.

- [ ] **Step 11: Commit**

```bash
git add apps/api/src/
git commit -m "feat(api): renomeia routers, schemas e handlers course → product"
```

---

### Task 4: Frontend — Types + API Client

**Files:**
- Modify: `apps/web/src/features/courses/types.ts`
- Modify: `apps/web/src/features/courses/hooks/useCourses.ts`
- Modify: `apps/web/src/features/courses/components/CourseCard.tsx`
- Modify: `apps/web/src/features/courses/components/CourseDrawer.tsx`
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/src/features/followup/types.ts`

- [ ] **Step 1: Atualizar features/courses/types.ts**

```typescript
// Renomear interfaces (mantém os campos iguais):
export interface Product {          // era Course
  id: string;
  name: string;
  hubla_id: string;
  is_active: boolean;
  flow_count: number;
  created_at: string;
  updated_at: string;
}

export interface CreateProductInput {  // era CreateCourseInput
  name: string;
  hubla_id: string;
  is_active?: boolean;
}

export interface UpdateProductInput {  // era UpdateCourseInput
  name?: string;
  hubla_id?: string;
  is_active?: boolean;
}
```

- [ ] **Step 2: Atualizar hooks/useCourses.ts**

```typescript
import { listProducts, createProduct, deleteProduct, updateProduct } from "@/lib/api";
import type { Product, CreateProductInput, UpdateProductInput } from "../types";

export function useProducts() {          // era useCourses
  const [products, setProducts] = useState<Product[]>([]);   // era courses
  // ...
  const create = useCallback(
    async (input: CreateProductInput): Promise<Product> => {
      const p = await createProduct(input);
      setProducts((prev) => [...prev, p].sort((a, b) => a.name.localeCompare(b.name)));
      return p;
    },
    []
  );
  const update = useCallback(
    async (id: string, input: UpdateProductInput): Promise<Product> => {
      const p = await updateProduct(id, input);
      setProducts((prev) => prev.map((x) => (x.id === id ? p : x)));
      return p;
    },
    []
  );
  const remove = useCallback(async (id: string): Promise<void> => {
    await deleteProduct(id);
    setProducts((prev) => prev.filter((x) => x.id !== id));
  }, []);

  return { products, loading, error, refresh, create, update, remove };
}
```

- [ ] **Step 3: Atualizar CourseCard.tsx → Product prop type**

```typescript
// Substituir:
import type { Product } from "../types";
interface Props { product: Product; ... }  // era course: Course
// Renomear prop "course" → "product" em todo o componente
```

- [ ] **Step 4: Atualizar CourseDrawer.tsx → Product prop type**

```typescript
import type { Product, CreateProductInput } from "../types";
interface Props {
  product: Product | null;  // era course
  // ...
  onCreate: (input: CreateProductInput) => Promise<Product>;
  onUpdate: (id: string, input: UpdateProductInput) => Promise<Product>;
}
// Todos os labels "Curso" → "Produto"
// "Nome do curso" → "Nome do produto"
// "Hubla ID" mantém igual
```

- [ ] **Step 5: Atualizar lib/api.ts**

```typescript
import type {
  Product,
  CreateProductInput,
  UpdateProductInput,
} from "@/features/courses/types";

export async function listProducts(): Promise<Product[]> {
  return apiFetch<Product[]>("/admin/products");
}
export async function createProduct(input: CreateProductInput): Promise<Product> {
  return apiFetch<Product>("/admin/products", {
    method: "POST",
    body: JSON.stringify(input),
  });
}
export async function updateProduct(id: string, input: UpdateProductInput): Promise<Product> {
  return apiFetch<Product>(`/admin/products/${id}`, {
    method: "PUT",
    body: JSON.stringify(input),
  });
}
export async function deletProduct(id: string): Promise<void> {
  return apiFetch<void>(`/admin/products/${id}`, { method: "DELETE" });
}
```

Remover as antigas `listCourses`, `createCourse`, `updateCourse`, `deleteCourse`.

- [ ] **Step 6: Atualizar features/followup/types.ts**

```typescript
export interface ProductSummary {   // era CourseSummary
  id: string;
  name: string;
  hubla_id: string;
}

export interface FollowupFlow {
  // ...
  product: ProductSummary;    // era course: CourseSummary
  // ...
}

export interface CreateFlowInput {
  name: string;
  product_id: string;    // era course_id
  is_active?: boolean;
}

export interface UpdateFlowInput {
  name?: string;
  product_id?: string;   // era course_id
  is_active?: boolean;
}
```

- [ ] **Step 7: Commit**

```bash
git add apps/web/src/
git commit -m "feat(web): renomeia Course → Product, useCourses → useProducts, /admin/courses → /admin/products"
```

---

### Task 5: Frontend — Página + Redirect

**Files:**
- Create: `apps/web/src/app/(admin)/products/page.tsx`
- Modify: `apps/web/src/app/(admin)/courses/page.tsx`
- Modify: `apps/web/src/features/followup/components/FlowDrawer.tsx`
- Modify: `apps/web/src/shared/components/layout/Sidebar.tsx`

- [ ] **Step 1: Criar página /products**

`apps/web/src/app/(admin)/products/page.tsx`:
```typescript
"use client";

import { useState } from "react";
import { useProducts } from "@/features/courses/hooks/useCourses";
import { ProductCard } from "@/features/courses/components/CourseCard";
import { ProductDrawer } from "@/features/courses/components/CourseDrawer";
import { useConfirm } from "@/shared/components/confirm/ConfirmProvider";
import { useToast } from "@/shared/hooks/useToast";
import type { Product } from "@/features/courses/types";

export default function ProductsPage() {
  const { products, loading, error, create, update, remove } = useProducts();
  const confirm = useConfirm();
  const toast = useToast();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<Product | null>(null);

  const openCreate = () => { setEditing(null); setDrawerOpen(true); };
  const openEdit = (p: Product) => { setEditing(p); setDrawerOpen(true); };
  const closeDrawer = () => { setDrawerOpen(false); setEditing(null); };

  const handleCreate = async (input: Parameters<typeof create>[0]) => {
    const p = await create(input);
    closeDrawer();
    return p;
  };

  const handleUpdate = async (id: string, input: Parameters<typeof update>[1]) => {
    const p = await update(id, input);
    closeDrawer();
    return p;
  };

  const handleDelete = async (p: Product) => {
    const ok = await confirm({
      title: "Excluir produto",
      description: `Excluir "${p.name}"? Esta ação não pode ser desfeita.`,
      confirmLabel: "Excluir",
      variant: "danger",
    });
    if (!ok) return;
    try {
      await remove(p.id);
      toast.success("Produto excluído");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Erro ao excluir produto";
      toast.error(msg);
    }
  };

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-h2 font-semibold text-on-surface">Produtos</h1>
          <p className="mt-1 text-sm text-on-surface-variant">
            Gerencie os produtos vinculados aos seus flows de follow-up.
          </p>
        </div>
        <button
          onClick={openCreate}
          className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-on-primary"
        >
          <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>add</span>
          Novo produto
        </button>
      </div>

      {loading && (
        <div className="flex items-center gap-2 text-on-surface-variant">
          <span className="material-symbols-outlined animate-spin" style={{ fontSize: "20px" }}>progress_activity</span>
          <span className="text-sm">Carregando...</span>
        </div>
      )}
      {error && <p className="text-sm text-error">{error}</p>}
      {!loading && products.length === 0 && (
        <p className="text-sm text-on-surface-variant">Nenhum produto cadastrado ainda.</p>
      )}

      <div className="flex flex-col gap-3">
        {products.map((p) => (
          <ProductCard
            key={p.id}
            product={p}
            onEdit={() => openEdit(p)}
            onDelete={() => void handleDelete(p)}
          />
        ))}
      </div>

      <ProductDrawer
        open={drawerOpen}
        product={editing}
        onClose={closeDrawer}
        onCreate={handleCreate}
        onUpdate={handleUpdate}
      />
    </div>
  );
}
```

- [ ] **Step 2: Redirecionar /courses → /products**

`apps/web/src/app/(admin)/courses/page.tsx` — substituir todo o conteúdo por:
```typescript
import { redirect } from "next/navigation";

export default function CoursesRedirectPage() {
  redirect("/products");
}
```

- [ ] **Step 3: Atualizar FlowDrawer — link "Cadastre primeiro"**

Em `apps/web/src/features/followup/components/FlowDrawer.tsx`, atualizar o link:
```typescript
// Antes:
<Link href="/courses" ...>Cadastre primeiro</Link>

// Depois:
<Link href="/products" ...>Cadastre primeiro</Link>
```

- [ ] **Step 4: Atualizar Sidebar**

Em `apps/web/src/shared/components/layout/Sidebar.tsx` — o label já foi atualizado para "Produtos" e ícone `inventory_2`. Só atualizar o href:
```typescript
{ label: "Produtos", href: "/products", icon: "inventory_2" },
```

- [ ] **Step 5: Verificar build**

```bash
cd apps/web
npm run build
```

Esperado: build limpo sem erros TypeScript.

- [ ] **Step 6: Commit final**

```bash
git add apps/web/src/
git commit -m "feat(web): adiciona página /products, redireciona /courses, atualiza links e Sidebar"
```

---

### Task 6: Limpar arquivos antigos (opcional, após validação em staging)

- [ ] **Step 1: Remover arquivos legados do backend**

```bash
rm apps/api/src/shared/domain/entities/course.py
rm apps/api/src/shared/domain/ports/course_repository.py
rm apps/api/src/shared/adapters/db/repositories/course_repo.py
rm apps/api/src/interface/http/routers/admin/courses.py
```

- [ ] **Step 2: Verificar que nenhum import quebrado persiste**

```bash
cd apps/api
uv run python -c "from main import app; print('OK')"
```

Esperado: `OK` sem erros de importação.

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "chore: remove arquivos legados course_* após rename para product_*"
```
