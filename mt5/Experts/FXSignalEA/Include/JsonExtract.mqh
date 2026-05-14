//+------------------------------------------------------------------+
//|                                                JsonExtract.mqh   |
//|  fx-signal-monitor 専用の超軽量 JSON フィールド抽出ヘルパ。       |
//|  full parser ではなく、文字列検索ベース。期待する JSON 構造は     |
//|  signals.json の決まった形式のみを想定する。                      |
//|                                                                  |
//|  対応する型: string / number / bool                              |
//|  対応する操作: トップレベル & ネスト 1 段の取り出し              |
//+------------------------------------------------------------------+
#property strict

//--- ヘルパ: pos 以降の最初の閉じ括弧 } を探す (ネスト対応)
int FindMatchingBrace(const string &json, int open_pos)
{
   int depth = 0;
   int n = StringLen(json);
   for(int i = open_pos; i < n; i++)
   {
      ushort c = StringGetCharacter(json, i);
      if(c == '"')
      {
         // 文字列内をスキップ
         i++;
         while(i < n && StringGetCharacter(json, i) != '"')
         {
            if(StringGetCharacter(json, i) == '\\') i++;
            i++;
         }
      }
      else if(c == '{') depth++;
      else if(c == '}')
      {
         depth--;
         if(depth == 0) return i;
      }
   }
   return -1;
}

//+------------------------------------------------------------------+
//| 指定キー "pair":"XXX" を含むトップレベルオブジェクトを返す。     |
//| signals.json の signals 配列を走査して該当ペアの JSON 部分を取得。|
//+------------------------------------------------------------------+
string JsonFindRecord(const string &json, const string pair_key)
{
   string needle = "\"pair\":\"" + pair_key + "\"";
   int pos = StringFind(json, needle, 0);
   if(pos < 0) return "";

   // 直前の { を遡って探す
   int start = pos;
   int depth = 0;
   while(start >= 0)
   {
      ushort c = StringGetCharacter(json, start);
      if(c == '}') depth++;
      else if(c == '{')
      {
         if(depth == 0) break;
         depth--;
      }
      start--;
   }
   if(start < 0) return "";

   int end = FindMatchingBrace(json, start);
   if(end < 0) return "";
   return StringSubstr(json, start, end - start + 1);
}

//+------------------------------------------------------------------+
//| ネストされたメソッドオブジェクト ("orz":{...}) を抜き出す。      |
//+------------------------------------------------------------------+
string JsonGetMethodObj(const string &record_json, const string method_key)
{
   string needle = "\"" + method_key + "\":{";
   int pos = StringFind(record_json, needle, 0);
   if(pos < 0) return "";
   int brace_pos = pos + StringLen(needle) - 1;
   int end = FindMatchingBrace(record_json, brace_pos);
   if(end < 0) return "";
   return StringSubstr(record_json, brace_pos, end - brace_pos + 1);
}

//+------------------------------------------------------------------+
//| "key":value (数値) を取得。見つからない / null なら nan_default。|
//+------------------------------------------------------------------+
double JsonGetNumber(const string &obj_json, const string key, double nan_default = EMPTY_VALUE)
{
   string needle = "\"" + key + "\":";
   int pos = StringFind(obj_json, needle, 0);
   if(pos < 0) return nan_default;
   pos += StringLen(needle);
   int n = StringLen(obj_json);
   // 空白スキップ
   while(pos < n && (StringGetCharacter(obj_json, pos) == ' ' || StringGetCharacter(obj_json, pos) == '\t'))
      pos++;
   // null チェック
   if(pos + 3 < n && StringSubstr(obj_json, pos, 4) == "null") return nan_default;
   // 数値の終わり (, または } または 改行 まで)
   int end = pos;
   while(end < n)
   {
      ushort c = StringGetCharacter(obj_json, end);
      if(c == ',' || c == '}' || c == ']' || c == '\n' || c == '\r' || c == ' ') break;
      end++;
   }
   string val = StringSubstr(obj_json, pos, end - pos);
   return StringToDouble(val);
}

//+------------------------------------------------------------------+
//| "key":"string" を取得。見つからなければ空文字。                   |
//+------------------------------------------------------------------+
string JsonGetString(const string &obj_json, const string key)
{
   string needle = "\"" + key + "\":\"";
   int pos = StringFind(obj_json, needle, 0);
   if(pos < 0) return "";
   pos += StringLen(needle);
   int end = pos;
   int n = StringLen(obj_json);
   while(end < n)
   {
      ushort c = StringGetCharacter(obj_json, end);
      if(c == '"' && StringGetCharacter(obj_json, end - 1) != '\\') break;
      end++;
   }
   return StringSubstr(obj_json, pos, end - pos);
}

//+------------------------------------------------------------------+
//| "key":true / false を取得。                                       |
//+------------------------------------------------------------------+
bool JsonGetBool(const string &obj_json, const string key, bool default_val = false)
{
   string needle = "\"" + key + "\":";
   int pos = StringFind(obj_json, needle, 0);
   if(pos < 0) return default_val;
   pos += StringLen(needle);
   int n = StringLen(obj_json);
   while(pos < n && (StringGetCharacter(obj_json, pos) == ' ' || StringGetCharacter(obj_json, pos) == '\t'))
      pos++;
   if(pos + 3 < n && StringSubstr(obj_json, pos, 4) == "true") return true;
   if(pos + 4 < n && StringSubstr(obj_json, pos, 5) == "false") return false;
   return default_val;
}

//+------------------------------------------------------------------+
//| "reasons":["a","b",...] を取得して文字列配列に格納                |
//| 戻り値: 取得した要素数                                              |
//+------------------------------------------------------------------+
int JsonGetStringArray(const string &obj_json, const string key, string &out[], int max_items = 8)
{
   string needle = "\"" + key + "\":[";
   int pos = StringFind(obj_json, needle, 0);
   if(pos < 0) { ArrayResize(out, 0); return 0; }
   pos += StringLen(needle);
   int n = StringLen(obj_json);
   string buf[];
   int count = 0;
   while(pos < n && count < max_items)
   {
      // 空白スキップ
      while(pos < n && (StringGetCharacter(obj_json, pos) == ' ' || StringGetCharacter(obj_json, pos) == ','))
         pos++;
      if(pos >= n) break;
      if(StringGetCharacter(obj_json, pos) == ']') break;
      if(StringGetCharacter(obj_json, pos) != '"')
      {
         pos++;
         continue;
      }
      pos++;
      int start = pos;
      while(pos < n && !(StringGetCharacter(obj_json, pos) == '"' && StringGetCharacter(obj_json, pos - 1) != '\\'))
         pos++;
      string s = StringSubstr(obj_json, start, pos - start);
      ArrayResize(buf, count + 1);
      buf[count] = s;
      count++;
      pos++;
   }
   ArrayResize(out, count);
   for(int i = 0; i < count; i++) out[i] = buf[i];
   return count;
}
//+------------------------------------------------------------------+
