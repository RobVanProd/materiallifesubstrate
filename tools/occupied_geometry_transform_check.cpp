// Independent exact-rational global input decoding. No candidate geometry.
// Boost rational/integer arithmetic and OpenSSL hashing; no Python decoder calls.
#include <boost/multiprecision/cpp_int.hpp>
#include <boost/rational.hpp>
#include <openssl/evp.h>
#include <array>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

using Z=boost::multiprecision::cpp_int;
using Q=boost::rational<Z>;
void require(bool b){if(!b)throw std::runtime_error("invalid independent input decode");}
std::string get(std::istream& f,std::size_t n){std::string b(n,'\0');f.read(b.data(),static_cast<std::streamsize>(n));require(f.good());return b;}
std::uint64_t integer(const std::string& b){require(b.size()<=8);std::uint64_t v=0;for(std::size_t i=0;i<b.size();++i)v|=std::uint64_t(static_cast<unsigned char>(b[i]))<<(8*i);return v;}
std::string word(std::uint64_t n,int bytes){std::string b;for(int i=0;i<bytes;++i)b.push_back(static_cast<char>((n>>(8*i))&255));return b;}
struct Number{Q value;std::string raw;};
Number read_q(std::istream& f){
    const auto sign=get(f,1),nl=get(f,4);const auto n=integer(nl);require(integer(sign)<=1&&n<=1024);
    const auto nb=get(f,n),dl=get(f,4);const auto d=integer(dl);require(d>0&&d<=1024);const auto db=get(f,d);
    require((nb.empty()||nb.back()!=0)&&db.back()!=0);
    Z num=0,den=0;
    for(auto i=nb.size();i>0;--i){num<<=8;num+=static_cast<unsigned char>(nb[i-1]);}
    for(auto i=db.size();i>0;--i){den<<=8;den+=static_cast<unsigned char>(db[i-1]);}
    require(num!=0||integer(sign)==0);if(integer(sign))num=-num;
    Q q(num,den);require(q.numerator()==num&&q.denominator()==den);
    return {q,sign+nl+nb+dl+db};
}
std::string magnitude(Z n){require(n>=0);std::vector<unsigned char> v;boost::multiprecision::export_bits(n,std::back_inserter(v),8,false);while(!v.empty()&&v.back()==0)v.pop_back();return {v.begin(),v.end()};}
std::string encode(const Q& q){Z num=q.numerator();const bool negative=num<0;if(negative)num=-num;const auto n=magnitude(num),d=magnitude(q.denominator());require(!d.empty());return std::string(1,negative?'\1':'\0')+word(n.size(),4)+n+word(d.size(),4)+d;}
struct Transform{std::array<std::array<Q,3>,3> m;std::array<Q,3>b,v;Q a;};
Transform transform(const std::filesystem::path& p){
    std::ifstream f(p,std::ios::binary);require(get(f,8)=="MLSOMG01");require(integer(get(f,4))==1&&integer(get(f,4))==9&&integer(get(f,8))==1);get(f,8);
    Transform t;for(auto& row:t.m)for(auto& x:row)x=read_q(f).value;for(auto& x:t.b)x=read_q(f).value;for(auto& x:t.v)x=read_q(f).value;t.a=read_q(f).value;require(t.a>0&&integer(get(f,1))==0);require(f.peek()==EOF);return t;
}
struct Hash{
    EVP_MD_CTX* context=EVP_MD_CTX_new();std::uint64_t bytes=0;std::string pending;
    Hash(){require(context&&EVP_DigestInit_ex(context,EVP_sha256(),nullptr)==1);pending.reserve(131072);}
    Hash(const Hash&)=delete;Hash& operator=(const Hash&)=delete;
    ~Hash(){EVP_MD_CTX_free(context);}
    void put(const std::string& s){bytes+=s.size();pending+=s;if(pending.size()>=65536)flush();}
    void flush(){if(!pending.empty()){require(EVP_DigestUpdate(context,pending.data(),pending.size())==1);pending.clear();}}
    std::string finish(){flush();unsigned char out[EVP_MAX_MD_SIZE];unsigned n=0;require(EVP_DigestFinal_ex(context,out,&n)==1&&n==32);std::ostringstream s;for(unsigned i=0;i<n;++i)s<<std::hex<<std::setw(2)<<std::setfill('0')<<unsigned(out[i]);return s.str();}
};
std::string component(const std::array<Number,3>& p,const Transform& t,int i,bool velocity){
    const Q shift=velocity?t.v[i]:t.b[i];int active=0,last=-1;
    for(int j=0;j<3;++j)if(t.m[i][j]!=0){++active;last=j;}
    if(active==1&&t.a==1&&shift==0&&(t.m[i][last]==1||t.m[i][last]==-1)){
        auto raw=p[last].raw;if(t.m[i][last]==-1&&p[last].value!=0)raw[0]^=1;return raw;
    }
    Q result=shift;for(int j=0;j<3;++j)if(t.m[i][j]!=0)result+=t.a*t.m[i][j]*p[j].value;return encode(result);
}
int main(int argc,char** argv){try{
    require(argc==3||argc==4);const bool plane=argc==4;std::array<Transform,30> ts;
    for(int i=0;i<30;++i){std::ostringstream name;name<<"transform-"<<std::setw(2)<<std::setfill('0')<<i<<".bin";ts[i]=transform(std::filesystem::path(argv[2])/name.str());}
    std::ifstream f(argv[1],std::ios::binary);const auto magic=get(f,8),schema=get(f,4),kind_wire=get(f,4),count_wire=get(f,8);
    require(magic=="MLSOMG01"&&integer(schema)==1);const auto kind=integer(kind_wire),count=integer(count_wire);require(kind==1||kind==5||kind==6||kind==7);
    std::array<Hash,30> hashes;for(auto& h:hashes)h.put(magic+schema+kind_wire+count_wire);
    for(std::uint64_t row=0;row<count;++row){
        if(kind==6){const auto d=read_q(f),v=read_q(f);for(int i=0;i<30;++i)hashes[i].put(encode(d.value*ts[i].a*ts[i].a)+encode(v.value*ts[i].a*ts[i].a*ts[i].a));continue;}
        const auto prefix=get(f,kind==7?17:8);std::array<Number,3> p;for(auto& x:p)x=read_q(f);
        if(plane&&kind!=7){p[2].value+=Q(2);p[2].raw=encode(p[2].value);}
        Number volume,amount;if(kind==5){volume=read_q(f);amount=read_q(f);}
        for(int i=0;i<30;++i){auto s=prefix;for(int j=0;j<3;++j)s+=component(p,ts[i],j,kind==7);
            if(kind==5)s+=(ts[i].a==1?volume.raw:encode(volume.value*ts[i].a*ts[i].a*ts[i].a))+amount.raw;
            hashes[i].put(s);}
    }
    require(f.peek()==EOF);for(int i=0;i<30;++i)std::cout<<i<<' '<<kind<<' '<<count<<' '<<hashes[i].bytes<<' '<<hashes[i].finish()<<'\n';
    return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
