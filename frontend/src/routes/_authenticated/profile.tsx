import { createFileRoute } from "@tanstack/react-router";
import { Panel, PageHeader } from "@/components/common";
import { useMe } from "@/lib/auth";
import { MEMBER_ROLE } from "@/lib/format";
import { pageHead } from "@/lib/meta";

export const Route = createFileRoute("/_authenticated/profile")({
  head: () => pageHead("Profile", "Your account and household details."),
  component: ProfilePage,
});

function ProfilePage() {
  const me = useMe();

  return (
    <>
      <PageHeader title="Your profile" />
      <Panel>
        <dl className="grid gap-5 sm:grid-cols-2">
          <div>
            <dt className="font-bold text-muted-foreground">Name</dt>
            <dd className="mt-1 text-lg">{me.display_name}</dd>
          </div>
          <div>
            <dt className="font-bold text-muted-foreground">Email</dt>
            <dd className="mt-1 text-lg">{me.email}</dd>
          </div>
          <div>
            <dt className="font-bold text-muted-foreground">Household</dt>
            <dd className="mt-1 text-lg">{me.household.name}</dd>
          </div>
          <div>
            <dt className="font-bold text-muted-foreground">Role</dt>
            <dd className="mt-1 text-lg">{MEMBER_ROLE[me.role]}</dd>
          </div>
        </dl>
      </Panel>
    </>
  );
}
