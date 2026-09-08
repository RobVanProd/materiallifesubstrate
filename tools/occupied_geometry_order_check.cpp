// Independent full-stream permutation/namespace audit; not a geometry evaluator.
#include <openssl/evp.h>
#include <algorithm>
#include <array>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>
using U=std::uint64_t;
void check(bool b){if(!b)throw std::runtime_error("independent order decode failed");}
U read(std::string_view s,std::size_t at,int n){check(at+n<=s.size());U v=0;for(int j=0;j<n;++j)v|=U(static_cast<unsigned char>(s[at+j]))<<(8*j);return v;}
void put(std::string& s,std::size_t at,U n){check(at+8<=s.size());for(int j=0;j<8;++j)s[at+j]=static_cast<char>((n>>(8*j))&255);}
struct Digest{
    EVP_MD_CTX* p=EVP_MD_CTX_new();U bytes=0;std::string buffer;
    Digest(){check(p&&EVP_DigestInit_ex(p,EVP_sha256(),nullptr)==1);buffer.reserve(131072);}
    ~Digest(){EVP_MD_CTX_free(p);}
    Digest(const Digest&)=delete;Digest& operator=(const Digest&)=delete;
    void flush(){if(!buffer.empty()){check(EVP_DigestUpdate(p,buffer.data(),buffer.size())==1);buffer.clear();}}
    void add(std::string_view s){bytes+=s.size();buffer.append(s);if(buffer.size()>=65536)flush();}
    std::string finish(){flush();unsigned char b[EVP_MAX_MD_SIZE];unsigned n=0;check(EVP_DigestFinal_ex(p,b,&n)==1&&n==32);std::ostringstream out;for(unsigned i=0;i<n;++i)out<<std::hex<<std::setfill('0')<<std::setw(2)<<unsigned(b[i]);return out.str();}
};
struct Random{
    U state;
    U draw(){U z=(state+=0x9e3779b97f4a7c15ULL);z=(z^(z>>30))*0xbf58476d1ce4e5b9ULL;z=(z^(z>>27))*0x94d049bb133111ebULL;return z^(z>>31);}
    U below(U b){check(b>0);const U threshold=(U(0)-b)%b;while(true){const U n=draw();if(n>=threshold)return n%b;}}
};
std::size_t skip(std::string_view s,std::size_t p){
    check(read(s,p,1)<=1);const auto n=read(s,p+1,4);check(n<=1024);p+=5+n;const auto d=read(s,p,4);check(d>0&&d<=1024&&p+4+d<=s.size());return p+4+d;
}
std::string renamed(std::string_view raw,U kind,U count,const std::array<U,6>& ns){
    std::string r(raw);if(kind==6)return r;
    auto flip=[&](std::size_t at,U total){const U old=read(r,at,8);check(old>0&&old<=total);put(r,at,total+1-old);};
    flip(0,kind==4?ns[2]:count);
    if(kind==2){for(int j=1;j<=4;++j)flip(8*j,ns[1]);}
    if(kind==3){const std::array<U,3> old{read(raw,8,8),read(raw,16,8),read(raw,24,8)};check(old[0]<old[1]&&old[1]<old[2]&&old[2]<=ns[1]);for(int j=0;j<3;++j)put(r,8+8*j,ns[1]+1-old[2-j]);}
    if(kind==4){flip(9,ns[3]);check(static_cast<unsigned char>(r[17])<=1);r[17]^=1;}
    if(kind==7){const auto target=read(r,8,1);check(target==1||target==5);flip(9,ns[target]);}
    return r;
}
int main(int argc,char** argv){try{
    check(argc==7);std::ifstream f(argv[1],std::ios::binary|std::ios::ate);check(f.good());const auto length=f.tellg();check(length>=24&&length<2LL*1024*1024*1024);f.seekg(0);
    std::string data(static_cast<std::size_t>(length),'\0');f.read(data.data(),length);check(f.good());check(data.substr(0,8)=="MLSOMG01"&&read(data,8,4)==1);
    const U kind=read(data,12,4),count=read(data,16,8);check(count<0x100000000ULL);
    std::array<U,6> ns{};ns[1]=std::stoull(argv[3]);ns[2]=std::stoull(argv[4]);ns[3]=std::stoull(argv[5]);ns[5]=std::stoull(argv[6]);
    const U width=kind==2?40:kind==3?32:kind==4?18:0;
    std::vector<U> offset;
    if(width)check(24+width*count==data.size());
    else{
        offset.reserve(count+1);std::size_t p=24;offset.push_back(p);
        for(U i=0;i<count;++i){
            if(kind==1||kind==5||kind==7){p+=kind==7?17:8;for(int j=0;j<(kind==5?5:3);++j)p=skip(data,p);}
            else if(kind==6)p=skip(data,skip(data,p));
            else if(kind==8)p+=17+read(data,p+9,8);
            else check(false);
            check(p<=data.size());offset.push_back(p);
        }
        check(p==data.size());
    }
    auto record=[&](U i){check(i<count);const U a=width?24+width*i:offset[i];const U b=width?a+width:offset[i+1];return std::string_view(data).substr(a,b-a);};
    std::array<Digest,3> hashes;for(auto& h:hashes)h.add(std::string_view(data).substr(0,24));
    for(U i=count;i>0;--i)hashes[0].add(record(i-1));
    std::vector<std::uint32_t> indices(count);std::iota(indices.begin(),indices.end(),0);Random rng{std::stoull(argv[2])};
    for(U i=count;i>1;--i)std::swap(indices[i-1],indices[rng.below(i)]);
    for(auto i:indices)hashes[1].add(record(i));
    if(kind==4){check(count==4*ns[2]);for(U t=ns[2];t>0;--t)for(U j=0;j<4;++j)hashes[2].add(renamed(record(4*(t-1)+j),kind,count,ns));}
    else for(U i=count;i>0;--i)hashes[2].add(renamed(record(i-1),kind,count,ns));
    for(int i=0;i<3;++i)std::cout<<30+i<<' '<<kind<<' '<<count<<' '<<hashes[i].bytes<<' '<<hashes[i].finish()<<'\n';
    return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
