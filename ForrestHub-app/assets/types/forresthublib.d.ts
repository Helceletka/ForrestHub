declare class ForrestHubLib {

  static getInstance(): ForrestHubLib;
  dbSetProject(project: string): void;
  dbResolveProjectName(projectOverride?: string | null): string;

  dbFetchAllData(): any;
  dbClearAllData(): void;

  dbVarSetKey(key: string, value: any, projectOverride?: string | null): void;
  dbVarGetKey(key: string, projectOverride?: string | null): any;
  dbVarKeyExists(key: string, projectOverride?: string | null): boolean;
  dbVarDeleteKey(key: string, projectOverride?: string | null): void;

  dbArrayAddRecord(arrayName: string, value: any, projectOverride?: string | null): void;
  dbArrayRemoveRecord(arrayName: string, recordId: string, projectOverride?: string | null): void;
  dbArrayUpdateRecord(arrayName: string, recordId: string, value: any, projectOverride?: string | null): void;
  dbArrayFetchAllRecords(arrayName: string, projectOverride?: string | null): any;
  dbArrayClearRecords(arrayName: string, projectOverride?: string | null): void;
  dbArrayFetchProjects(): any[];
}
declare const forrestHubLib: ForrestHubLib;
declare const ENV: Record<string, string>;
