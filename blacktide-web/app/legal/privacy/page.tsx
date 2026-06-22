import LegalLayout, { Clause } from "@/components/LegalLayout";
import { LEGAL_DOCS } from "@/lib/legalContent";
export default function Page() {
  const doc = LEGAL_DOCS.privacy;
  return (
    <LegalLayout title={doc.title} updated={doc.updated}>
      {doc.sections.map(([h, p]) => <Clause key={h} title={h}><p>{p}</p></Clause>)}
    </LegalLayout>
  );
}
