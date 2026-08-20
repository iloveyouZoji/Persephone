// Optional C++ helper to read results from SQLite polls.db
// Compile: g++ -std=c++17 cpp/read_results.cpp -lsqlite3 -o read_results
#include <sqlite3.h>
#include <iostream>
#include <string>

int main(int argc, char** argv){
    const char* dbfile = "polls.db";
    if(argc>1) dbfile = argv[1];
    sqlite3* db;
    if(sqlite3_open(dbfile, &db)){
        std::cerr<<"Can't open DB: "<<sqlite3_errmsg(db)<<"\n";
        return 1;
    }
    const char* sql = "SELECT p.id, p.title, c.code, c.label, COUNT(v.id) as votes "
                      "FROM polls p "
                      "LEFT JOIN choices c ON c.poll_id=p.id "
                      "LEFT JOIN votes v ON v.choice_id=c.id "
                      "GROUP BY p.id, c.id "
                      "ORDER BY p.created_at DESC;";
    sqlite3_stmt* stmt;
    if(sqlite3_prepare_v2(db, sql, -1, &stmt, nullptr)!=SQLITE_OK){
        std::cerr<<"Query prepare failed\n";
        return 1;
    }
    std::cout<<"Poll results:\n";
    while(sqlite3_step(stmt)==SQLITE_ROW){
        int pid = sqlite3_column_int(stmt,0);
        const unsigned char* title = sqlite3_column_text(stmt,1);
        const unsigned char* code = sqlite3_column_text(stmt,2);
        const unsigned char* label = sqlite3_column_text(stmt,3);
        int votes = sqlite3_column_int(stmt,4);
        std::cout<<"Poll "<<pid<<" - "<<(title? (const char*)title : "N/A")<<" : "<<(code? (const char*)code:"?")<<"="<<(label? (const char*)label:"?")<<" -> "<<votes<<"\n";
    }
    sqlite3_finalize(stmt);
    sqlite3_close(db);
    return 0;
}