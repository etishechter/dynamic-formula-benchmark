using System;
using System.Collections.Generic;
using System.Diagnostics;
using Microsoft.Data.Sqlite;

namespace SolveCSharp;

/// <summary>
/// C# solution: computes dynamic formulas using a hand-written expression
/// parser/evaluator (see Formula.cs). Each formula is parsed once into an
/// AST, then evaluated once per row of t_data - the .NET counterpart to the
/// Python "compile once, eval per row" approach.
///
/// Usage:
///     dotnet run -- --db ..\..\payments.db
/// </summary>
internal static class Program
{
    private const string Method = "CSharp-parser";

    private record Formula(long TargilId, Node Targil, Node? Tnai, Node? FalseTargil);
    private record DataRow(long DataId, double A, double B, double C, double D);

    private static void Main(string[] args)
    {
        string dbPath = "../../payments.db";
        for (int i = 0; i < args.Length - 1; i++)
        {
            if (args[i] == "--db") dbPath = args[i + 1];
        }

        using var conn = new SqliteConnection($"Data Source={dbPath}");
        conn.Open();
        using (var pragma = conn.CreateCommand())
        {
            pragma.CommandText = "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;";
            pragma.ExecuteNonQuery();
        }

        using (var cleanup = conn.CreateCommand())
        {
            cleanup.CommandText = "DELETE FROM t_results WHERE method = $m; DELETE FROM t_log WHERE method = $m;";
            cleanup.Parameters.AddWithValue("$m", Method);
            cleanup.ExecuteNonQuery();
        }

        var formulas = LoadFormulas(conn);
        var dataRows = LoadData(conn);
        Console.WriteLine($"Loaded {formulas.Count} formulas and {dataRows.Count:N0} data rows");

        double totalEval = 0, totalSave = 0;
        foreach (var formula in formulas)
        {
            var results = new List<(long DataId, long TargilId, double Result)>(dataRows.Count);
            var sw = Stopwatch.StartNew();

            foreach (var row in dataRows)
            {
                Node chosen = formula.Targil;
                if (formula.Tnai is not null)
                {
                    bool conditionTrue = formula.Tnai.Eval(row.A, row.B, row.C, row.D) != 0.0;
                    chosen = conditionTrue ? formula.Targil : formula.FalseTargil!;
                }
                double result = chosen.Eval(row.A, row.B, row.C, row.D);
                results.Add((row.DataId, formula.TargilId, result));
            }
            sw.Stop();
            double elapsedSeconds = sw.Elapsed.TotalSeconds;
            totalEval += elapsedSeconds;

            var swSave = Stopwatch.StartNew();
            SaveResults(conn, results, elapsedSeconds, formula.TargilId);
            swSave.Stop();
            totalSave += swSave.Elapsed.TotalSeconds;

            Console.WriteLine($"  targil_id={formula.TargilId,2}  rows={dataRows.Count,7:N0}  eval={elapsedSeconds:F4}s  save={swSave.Elapsed.TotalSeconds:F4}s");
        }
        Console.WriteLine($"TOTAL eval={totalEval:F4}s  save={totalSave:F4}s");
    }

    private static List<Formula> LoadFormulas(SqliteConnection conn)
    {
        var formulas = new List<Formula>();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT targil_id, targil, tnai, targil_false FROM t_targil";
        using var reader = cmd.ExecuteReader();
        while (reader.Read())
        {
            long targilId = reader.GetInt64(0);
            string targil = reader.GetString(1);
            string? tnai = reader.IsDBNull(2) ? null : reader.GetString(2);
            string? falseTargil = reader.IsDBNull(3) ? null : reader.GetString(3);

            formulas.Add(new Formula(
                targilId,
                FormulaParser.Parse(targil),
                tnai is null ? null : FormulaParser.Parse(tnai),
                falseTargil is null ? null : FormulaParser.Parse(falseTargil)));
        }
        return formulas;
    }

    private static List<DataRow> LoadData(SqliteConnection conn)
    {
        var rows = new List<DataRow>();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT data_id, a, b, c, d FROM t_data";
        using var reader = cmd.ExecuteReader();
        while (reader.Read())
        {
            rows.Add(new DataRow(
                reader.GetInt64(0),
                reader.GetDouble(1),
                reader.GetDouble(2),
                reader.GetDouble(3),
                reader.GetDouble(4)));
        }
        return rows;
    }

    private const int InsertBatchSize = 500;

    private static SqliteCommand BuildBatchInsertCommand(SqliteConnection conn, SqliteTransaction tx, int rowCount)
    {
        var cmd = conn.CreateCommand();
        cmd.Transaction = tx;

        var valuesSql = new System.Text.StringBuilder();
        for (int i = 0; i < rowCount; i++)
        {
            if (i > 0) valuesSql.Append(',');
            valuesSql.Append($"($d{i},$t{i},$method,$r{i})");
            cmd.Parameters.Add(new SqliteParameter($"$d{i}", SqliteType.Integer));
            cmd.Parameters.Add(new SqliteParameter($"$t{i}", SqliteType.Integer));
            cmd.Parameters.Add(new SqliteParameter($"$r{i}", SqliteType.Real));
        }
        cmd.Parameters.AddWithValue("$method", Method);
        cmd.CommandText = $"INSERT INTO t_results (data_id, targil_id, method, result) VALUES {valuesSql}";
        cmd.Prepare();
        return cmd;
    }

    private static void SaveResults(
        SqliteConnection conn,
        List<(long DataId, long TargilId, double Result)> results,
        double elapsedSeconds,
        long targilId)
    {
        using var tx = conn.BeginTransaction();

        // Batched multi-row INSERT (chunks of InsertBatchSize) instead of one
        // ExecuteNonQuery per row - cuts per-statement parse/step overhead
        // dramatically, which matters once t_data reaches ~1,000,000 rows.
        // The full-size batch command is built and prepared once, then reused
        // (only its parameter values change) for every full chunk.
        SqliteCommand? fullBatchCmd = null;
        try
        {
            int offset = 0;
            while (offset < results.Count)
            {
                int chunkSize = Math.Min(InsertBatchSize, results.Count - offset);
                SqliteCommand cmd;

                if (chunkSize == InsertBatchSize)
                {
                    if (fullBatchCmd is null)
                    {
                        fullBatchCmd = BuildBatchInsertCommand(conn, tx, InsertBatchSize);
                    }
                    cmd = fullBatchCmd;
                }
                else
                {
                    cmd = BuildBatchInsertCommand(conn, tx, chunkSize);
                }

                // Indexed access (not by-name lookup) - the parameters were
                // added in (d,t,r) triples in this exact order, so position
                // i*3 + {0,1,2} is O(1) instead of an O(n) name search.
                for (int i = 0; i < chunkSize; i++)
                {
                    cmd.Parameters[i * 3].Value = results[offset + i].DataId;
                    cmd.Parameters[i * 3 + 1].Value = results[offset + i].TargilId;
                    cmd.Parameters[i * 3 + 2].Value = results[offset + i].Result;
                }
                cmd.ExecuteNonQuery();

                if (chunkSize != InsertBatchSize) cmd.Dispose();
                offset += chunkSize;
            }
        }
        finally
        {
            fullBatchCmd?.Dispose();
        }

        using (var insertLog = conn.CreateCommand())
        {
            insertLog.Transaction = tx;
            insertLog.CommandText =
                "INSERT INTO t_log (targil_id, method, run_time) VALUES ($targil_id, $method, $run_time)";
            insertLog.Parameters.AddWithValue("$targil_id", targilId);
            insertLog.Parameters.AddWithValue("$method", Method);
            insertLog.Parameters.AddWithValue("$run_time", elapsedSeconds);
            insertLog.ExecuteNonQuery();
        }

        tx.Commit();
    }
}
