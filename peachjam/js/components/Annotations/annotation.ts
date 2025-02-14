export interface ITargetSelector {
    type: string;
    end: number;
    start: number;
}

export interface IAnnotation {
    id: number;
    document: number;
    // eslint-disable-next-line camelcase
    target_selectors: ITargetSelector[];
    // eslint-disable-next-line camelcase
    target_id: string;
    text: string;
}
