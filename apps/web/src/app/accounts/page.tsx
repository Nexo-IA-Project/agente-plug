// apps/web/src/app/accounts/page.tsx
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Users } from "lucide-react";

export default function AccountsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Accounts</h1>
        <p className="text-muted-foreground">
          Gestão de contas e configurações por tenant.
        </p>
      </div>

      <Card className="max-w-md">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base font-semibold">
            <Users className="h-4 w-4" />
            Em breve
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            O gerenciamento de accounts está sendo desenvolvido. Aqui você
            poderá criar novos tenants, configurar integrações (Cademi, Hubla,
            ChatNexo) e definir as políticas de reembolso por conta.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
