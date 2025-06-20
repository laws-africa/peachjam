/* eslint-disable camelcase */

export interface IProvisionEnrichment {
    id: number;
    text: string;
    judgment: object;
    date_deemed_unconstitutional: string;
    end_of_suspension_period: string;
    resolved: boolean;
    resolving_amendment_work: object;
    provision_eid: string;
}
