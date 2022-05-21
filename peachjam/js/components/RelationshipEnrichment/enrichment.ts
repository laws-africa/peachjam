export interface IRelationshipEnrichmentDocument {
  title: string;
  // eslint-disable-next-line camelcase
  expression_frbr_uri: string;
  language: string;
  date: string;
}

export interface IRelationshipEnrichment {
  id: number;
  predicate: object;
  // eslint-disable-next-line camelcase
  subject_work_frbr_uri: string;
  // eslint-disable-next-line camelcase
  subject_target_id: string | null;
  // eslint-disable-next-line camelcase
  subject_documents: IRelationshipEnrichmentDocument[];

  // eslint-disable-next-line camelcase
  object_work_frbr_uri: string;
  // eslint-disable-next-line camelcase
  object_target_id: string | null;
  // eslint-disable-next-line camelcase
  object_documents: IRelationshipEnrichmentDocument[];
}

export function bestDocument (docs: IRelationshipEnrichmentDocument[], language: string): IRelationshipEnrichmentDocument | null {
  if (!docs.length) {
    return null;
  }

  // sort docs by date, descending order
  const sorted = [...docs].sort((a, b) => -a.date.localeCompare(b.date));

  // find the first doc in our language, or fall back to the first doc
  return sorted.find(d => d.language === language) || sorted[0];
}
