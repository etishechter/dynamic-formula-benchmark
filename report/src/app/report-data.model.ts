export interface FormulaTiming {
  targilId: number;
  targil: string;
  tnai: string | null;
  falseTargil: string | null;
  kind: 'conditional' | 'unconditional';
  times: Record<string, number>;
}

export interface ReportData {
  generatedAt: string;
  dataRowCount: number;
  methods: string[];
  totalsByMethod: Record<string, number>;
  formulas: FormulaTiming[];
  resultsMismatchCount: number;
}
