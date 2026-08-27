import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { ReportData, FormulaTiming } from './report-data.model';

interface MethodInfo {
  label: string;
  description: string;
  color: string;
}

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css',
})
export class AppComponent implements OnInit {
  report: ReportData | null = null;
  loading = true;
  error: string | null = null;

  // Fixed method metadata: consistent color + a short explanation of how
  // each method computes the dynamic formulas (required by the assignment).
  readonly methodInfo: Record<string, MethodInfo> = {
    'Python-eval': {
      label: 'Python (eval)',
      description:
        'כל נוסחה מתקומפלת פעם אחת (compile) ולאחר מכן מורצת בלולאה עם eval() על כל רשומה בנפרד - פירוש (interpretation) שורה-שורה בזמן ריצה.',
      color: '#3776AB',
    },
    'SQL-native': {
      label: 'SQL (דינמי, מנוע ה-DB)',
      description:
        'הנוסחה מתורגמת פעם אחת למחרוזת SQL דינמית (מקביל ל-EXECUTE IMMEDIATE / sp_executesql) ומורצת כשאילתת SELECT יחידה שמחשבת את כל השורות בבת אחת בתוך מנוע מסד הנתונים.',
      color: '#f2a900',
    },
    'CSharp-parser': {
      label: 'C# (מפענח נוסחאות עצמאי)',
      description:
        'הנוסחה נפרסת (parse) פעם אחת לעץ תחביר (AST) על ידי מפענח שנכתב ידנית, ולאחר מכן העץ מוערך (Eval) עבור כל רשומה - קוד מנוהל (.NET) שרץ ללא ספריות חיצוניות.',
      color: '#8e44ad',
    },
  };

  constructor(private http: HttpClient) {}

  ngOnInit(): void {
    this.http.get<ReportData>('report-data.json').subscribe({
      next: (data) => {
        this.report = data;
        this.loading = false;
      },
      error: (err) => {
        this.error = 'לא נמצא report-data.json. יש להריץ קודם: python scripts/generate_report_data.py';
        this.loading = false;
        console.error(err);
      },
    });
  }

  info(method: string): MethodInfo {
    return this.methodInfo[method] ?? { label: method, description: '', color: '#888' };
  }

  formatTime(seconds: number | undefined): string {
    if (seconds === undefined) return '-';
    if (seconds < 1) return `${(seconds * 1000).toFixed(1)} ms`;
    return `${seconds.toFixed(3)} s`;
  }

  maxTimeInFormula(f: FormulaTiming): number {
    return Math.max(...Object.values(f.times), 0.0001);
  }

  barWidth(time: number | undefined, max: number): string {
    if (!time) return '0%';
    return `${Math.max((time / max) * 100, 2)}%`;
  }

  get methodsSortedByTotal(): string[] {
    if (!this.report) return [];
    return [...this.report.methods].sort(
      (a, b) => this.report!.totalsByMethod[a] - this.report!.totalsByMethod[b]
    );
  }

  get maxTotal(): number {
    if (!this.report) return 1;
    return Math.max(...Object.values(this.report.totalsByMethod), 0.0001);
  }

  get fastestMethod(): string | null {
    return this.methodsSortedByTotal[0] ?? null;
  }

  get resultsVerified(): boolean {
    return (this.report?.resultsMismatchCount ?? -1) === 0;
  }
}
