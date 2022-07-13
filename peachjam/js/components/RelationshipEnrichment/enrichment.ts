export interface IRelationshipEnrichmentDocument {
  title: string;
  // eslint-disable-next-line camelcase
  expression_frbr_uri: string;
  language: string;
  language3: string;
  date: string;
}

export interface IRelationshipEnrichmentWork {
  // eslint-disable-next-line camelcase
  frbr_uri: string;
}

export interface IRelationshipPredicate {
  id: number;
  verb: string;
  // eslint-disable-next-line camelcase
  reverse_verb: string;
}

export interface IRelationshipEnrichment {
  id: number;
  predicate: IRelationshipPredicate;
  // eslint-disable-next-line camelcase
  subject_work: IRelationshipEnrichmentWork;
  // eslint-disable-next-line camelcase
  subject_target_id: string | null;
  // eslint-disable-next-line camelcase
  subject_documents: IRelationshipEnrichmentDocument[];

  // eslint-disable-next-line camelcase
  object_work: IRelationshipEnrichmentWork;
  // eslint-disable-next-line camelcase
  object_target_id: string | null;
  // eslint-disable-next-line camelcase
  object_documents: IRelationshipEnrichmentDocument[];
}

export function reverseRelationship (relationship: IRelationshipEnrichment) {
  for (const attr of ['work', 'target_id', 'documents']) {
    // @ts-ignore
    const val = relationship[`subject_${attr}`];
    // @ts-ignore
    relationship[`subject_${attr}`] = relationship[`object_${attr}`]
    // @ts-ignore
    relationship[`object_${attr}`] = val;
  }
}

export function bestDocument (docs: IRelationshipEnrichmentDocument[], language: string): IRelationshipEnrichmentDocument | null {
  if (!docs.length) {
    return null;
  }

  // sort docs by date, descending order
  const sorted = [...docs].sort((a, b) => -a.date.localeCompare(b.date));

  // find the first doc in our language, or fall back to the first doc
  return sorted.find(d => d.language3 === language) || sorted[0];
}
